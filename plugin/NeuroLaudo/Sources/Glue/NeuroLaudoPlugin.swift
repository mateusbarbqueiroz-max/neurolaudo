//  NeuroLaudo — ponto de entrada do complemento: registra os comandos no IsiX.
//
//  Config/Info.plist aponta para esta classe em NSPrincipalClass, como
//  $(PRODUCT_MODULE_NAME).$(ISIX_PLUGIN_ENTRY_CLASS) = NeuroLaudo.NeuroLaudoPlugin.

#if canImport(AppKit)
import AppKit
#endif
import Foundation
import IsiXPluginKit

/// O que o complemento mostra ao usuário. A implementação com AppKit fica em
/// UI/AppKitPresenter.swift; os testes usam `SilentPresenter`.
@MainActor protocol Presenting: AnyObject {
    /// Mostra um resultado, com opção de copiar o texto para o laudo.
    func show(_ outcome: MeasureOutcome, in window: NSWindow?)
    /// Pergunta em quantos cortes o hematoma aparece; `nil` se o usuário cancelou.
    func askSliceCount(intervalMM: Double, in window: NSWindow?, completion: @escaping @MainActor @Sendable (Double?) -> Void)
    /// Abre o painel do ASPECTS.
    func showAspects()
    /// Fecha o que estiver aberto, ao desativar o complemento.
    func closeAll()
}

/// Guarda o que seria mostrado, sem interface: para testes e para compilar sem AppKit.
@MainActor final class SilentPresenter: Presenting {
    var shown: [MeasureOutcome] = []
    var sliceCountAnswer: Double?
    var aspectsRequests = 0

    func show(_ outcome: MeasureOutcome, in window: NSWindow?) { shown.append(outcome) }

    func askSliceCount(intervalMM: Double, in window: NSWindow?, completion: @escaping @MainActor @Sendable (Double?) -> Void) {
        completion(sliceCountAnswer)
    }

    func showAspects() { aspectsRequests += 1 }

    func closeAll() {}
}

@MainActor enum PresenterFactory {
    static func make() -> Presenting {
        #if canImport(AppKit)
        return AppKitPresenter()
        #else
        return SilentPresenter()
        #endif
    }
}

public final class NeuroLaudoPlugin: IsiXPlugin {
    /// Identificadores dos comandos: o IsiX os distingue por eles, não pelos títulos.
    enum Command {
        static let evans = "medida-evans"
        static let midline = "medida-linha-media"
        static let hematoma = "medida-abc2"
        static let aspects = "medida-aspects"
        static let protocolAuto = "protocolo-neuro"
        static let comparePrior = "comparar-anterior"
        static let autoOpenToggle = "abrir-ao-chegar"
        static let about = "sobre"
    }

    static let aboutText = """
        Janelas de TC (menu Plugins › Image Filters, ou ⌃⌥ + número sobre a imagem): \
        1 Encéfalo, 2 AVC, 3 Subdural, 4 Osso, 5 Angio-TC, 6 Partes moles.

        Medidas (menu Plugins › ROI Tools), sempre no corte atual:
        • Índice de Evans: duas linhas, cornos frontais e diâmetro interno do crânio.
        • Desvio da linha média: uma linha sobre a linha média ideal e um ponto no septo pelúcido.
        • Volume de hematoma (ABC/2): duas linhas perpendiculares no corte de maior hematoma.
        • ASPECTS: painel com as dez regiões.

        Exames (menu Plugins › Database):
        • Protocolo de neuro: abre as séries do exame na ordem do protocolo.
        • Comparar com exame anterior: abre a série equivalente do exame anterior.
        • Abrir exame ao chegar: liga ou desliga a abertura automática do exame que chega \
        pelo botão do PACS. Vem ligada.

        Uso em apoio à leitura. Sem certificação para diagnóstico.
        """

    private var context: IsiXPluginContext?
    private var keyObservation: IsiXObservation?
    /// Trocado pelos testes; criado na ativação se ninguém o definiu.
    var presenter: Presenting?
    /// Onde ficam as opções. Trocado pelos testes; por padrão, as preferências do IsiX.
    var settings: SettingsStore?
    private var eventObservation: IsiXObservation?
    private var autoOpen: AutoOpen?

    public init() {}

    // MARK: ciclo de vida

    public func activate(with context: IsiXPluginContext) throws {
        self.context = context
        if presenter == nil { presenter = PresenterFactory.make() }
        autoOpen = AutoOpen(store: settings ?? DefaultsStore())

        try registerWindowCommands(context)
        try registerMeasureCommands(context)
        try registerStudyCommands(context)

        try context.register(IsiXCommand(id: Command.about, title: "NeuroLaudo: ajuda", placement: .other,
                                         requirement: .none)) { [weak self] invocation in
            let version = self?.context?.info.version ?? ""
            self?.presenter?.show(MeasureOutcome(title: "NeuroLaudo \(version)", text: Self.aboutText), in: invocation.parentWindow)
        }
        // Prova de que o IsiX carregou e ativou o complemento; ver PluginLog.
        PluginLog.note("NeuroLaudo \(context.info.version) ativado, \(NeuroWindowPresets.ct.count + 8) comandos")
    }

    public func deactivate() {
        keyObservation?.invalidate()
        keyObservation = nil
        eventObservation?.invalidate()
        eventObservation = nil
        autoOpen = nil
        presenter?.closeAll()
        presenter = nil
        context = nil
    }

    // MARK: janelas

    private func registerWindowCommands(_ context: IsiXPluginContext) throws {
        for preset in NeuroWindowPresets.ct {
            try context.register(IsiXCommand(id: preset.id, title: preset.title, placement: .imageFilters,
                                             requirement: .viewer)) { invocation in
                guard let viewer = invocation.viewer else { return }
                try WindowCommands.apply(preset, to: viewer)
            }
        }
        // ⌃⌥ + número sobre a imagem. Qualquer outra tecla segue para o IsiX.
        keyObservation = try context.interceptInput([.keyDown]) { [weak self] event in
            guard let preset = WindowCommands.preset(forKeyCode: event.keyCode, modifiers: event.modifierFlags),
                  let viewer = try? self?.context?.viewer(withID: event.viewerID) else { return false }
            return (try? WindowCommands.apply(preset, to: viewer)) != nil
        }
    }

    // MARK: medidas

    private func registerMeasureCommands(_ context: IsiXPluginContext) throws {
        try context.register(IsiXCommand(id: Command.evans, title: "Índice de Evans", placement: .roiTools,
                                         requirement: .viewer)) { [weak self] invocation in
            guard let viewer = invocation.viewer else { return }
            self?.presenter?.show(try ViewerMeasures.evans(in: viewer), in: invocation.parentWindow)
        }
        try context.register(IsiXCommand(id: Command.midline, title: "Desvio da linha média", placement: .roiTools,
                                         requirement: .viewer)) { [weak self] invocation in
            guard let viewer = invocation.viewer else { return }
            self?.presenter?.show(try ViewerMeasures.midlineShift(in: viewer), in: invocation.parentWindow)
        }
        try context.register(IsiXCommand(id: Command.hematoma, title: "Volume de hematoma (ABC/2)…", placement: .roiTools,
                                         requirement: .viewer)) { [weak self] invocation in
            guard let self, let viewer = invocation.viewer else { return }
            let inputs = try ViewerMeasures.hematomaInputs(in: viewer)
            let window = invocation.parentWindow
            self.presenter?.askSliceCount(intervalMM: inputs.sliceIntervalMM, in: window) { [weak self] count in
                guard let self, let count else { return }
                let outcome: MeasureOutcome
                do {
                    outcome = try ViewerMeasures.hematoma(inputs, sliceCount: count, in: viewer)
                } catch {
                    outcome = MeasureOutcome(title: "Volume de hematoma (ABC/2)", text: Self.describe(error))
                }
                self.presenter?.show(outcome, in: window)
            }
        }
        try context.register(IsiXCommand(id: Command.aspects, title: "ASPECTS…", placement: .roiTools,
                                         requirement: .none)) { [weak self] _ in
            self?.presenter?.showAspects()
        }
    }

    // MARK: exames

    private func registerStudyCommands(_ context: IsiXPluginContext) throws {
        try context.register(IsiXCommand(id: Command.protocolAuto, title: "Protocolo de neuro (RM ou TC)", placement: .database,
                                         requirement: .none)) { [weak self] invocation in
            guard let self, let context = self.context else { return }
            let viewer = invocation.viewer ?? (try? context.frontmostViewer())
            let outcome = try ProtocolCommands.apply(nil, context: context, viewer: viewer)
            // Só interrompe o usuário se faltou alguma série do protocolo.
            if outcome.text.contains("Não encontrei") {
                self.presenter?.show(outcome, in: invocation.parentWindow)
            }
        }
        try context.register(IsiXCommand(id: Command.comparePrior, title: "Comparar com exame anterior", placement: .database,
                                         requirement: .none)) { [weak self] invocation in
            guard let self, let context = self.context else { return }
            let viewer = invocation.viewer ?? (try? context.frontmostViewer())
            _ = try ProtocolCommands.compareWithPrior(context: context, viewer: viewer)
        }
        try context.register(IsiXCommand(id: Command.autoOpenToggle, title: "Abrir exame ao chegar: ligar ou desligar",
                                         placement: .database, requirement: .none)) { [weak self] invocation in
            guard let self, let autoOpen = self.autoOpen else { return }
            autoOpen.isEnabled.toggle()
            let text = autoOpen.isEnabled
                ? "Ligada: o exame que chegar sozinho pela rede abre já arrumado pelo protocolo de neuro."
                : "Desligada: os exames chegam ao banco de dados e não abrem sozinhos."
            self.presenter?.show(MeasureOutcome(title: "Abertura automática", text: text), in: invocation.parentWindow)
        }
        // O exame que chega (por exemplo, pelo botão do PACS) abre sozinho.
        eventObservation = try context.observe([.imagesAdded]) { [weak self] event in
            guard let self, let context = self.context else { return }
            self.autoOpen?.handle(event, context: context)
        }
    }

    // MARK: apoio

    static func describe(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? String(describing: error)
    }
}
