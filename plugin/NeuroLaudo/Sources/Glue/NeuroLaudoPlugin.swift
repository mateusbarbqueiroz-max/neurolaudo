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
        static let volumetry = "volumetria"
        static let about = "sobre"
        static let selfTest = "autoteste"
        static let selfTestMiddle = "autoteste-meio"
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
        • Abrir exame ao chegar: liga ou desliga a abertura automática, pelo protocolo de neuro, \
        do exame que chega pela rede. Vem ligada. Se o próprio IsiX já abriu o exame (botão do PACS, \
        IsiX 6.0.4 ou mais novo), o complemento não abre outras janelas: use o Protocolo de neuro.

        Volumetria cerebral (menu Plugins › Image Filters), com a série T1 volumétrica sem contraste aberta: \
        mede hipocampos, amígdalas, tálamos, ventrículos, córtex e substância branca, compara com adultos \
        saudáveis da mesma idade e sexo e grava no exame um relatório e um mapa colorido. Leva alguns minutos \
        e exige o motor de volumetria instalado. Uso em pesquisa, não validado para diagnóstico.

        Uso em apoio à leitura. Sem certificação para diagnóstico.
        """

    private var context: IsiXPluginContext?
    private var keyObservation: IsiXObservation?
    /// Trocado pelos testes; criado na ativação se ninguém o definiu.
    var presenter: Presenting?
    /// Onde ficam as opções. Trocado pelos testes; por padrão, as preferências do IsiX.
    var settings: SettingsStore?
    /// Espera da abertura automática (ver AutoOpen). Os testes usam zero.
    var autoOpenDelay: TimeInterval = AutoOpen.defaultDelay
    private var eventObservation: IsiXObservation?
    private var autoOpen: AutoOpen?
    /// Quem roda a volumetria. Trocado pelos testes; por padrão, o motor instalado no Mac.
    var engine: (any VolumetryEngine)?
    private var volumetryTask: IsiXTask?

    public init() {}

    // MARK: ciclo de vida

    public func activate(with context: IsiXPluginContext) throws {
        self.context = context
        if presenter == nil { presenter = PresenterFactory.make() }
        let store = settings ?? DefaultsStore()
        autoOpen = AutoOpen(store: store, delay: autoOpenDelay)

        try registerWindowCommands(context)
        try registerMeasureCommands(context)
        try registerStudyCommands(context)
        try context.register(IsiXCommand(id: Command.volumetry, title: "Volumetria cerebral (pesquisa)…",
                                         placement: .imageFilters, requirement: .viewer)) { [weak self] invocation in
            guard let self, let context = self.context else { return }
            guard let viewer = invocation.viewer else {
                PluginLog.note("volumetria: comando chamado sem série aberta")
                return
            }
            do {
                try self.startVolumetry(in: viewer, context: context)
            } catch {
                PluginLog.note("volumetria: recusada. \(Self.describe(error))")
                throw error
            }
        }

        try context.register(IsiXCommand(id: Command.about, title: "NeuroLaudo: ajuda", placement: .other,
                                         requirement: .none)) { [weak self] invocation in
            let version = self?.context?.info.version ?? ""
            self?.presenter?.show(MeasureOutcome(title: "NeuroLaudo \(version)", text: Self.aboutText), in: invocation.parentWindow)
        }
        // Só no teste automático (IsiX aberto com -NeuroLaudoAutoteste YES).
        let selfTest = store.bool(forKey: SelfTest.settingsKey) == true
        if selfTest {
            try context.register(IsiXCommand(id: Command.selfTest, title: "NeuroLaudo: autoteste", placement: .other,
                                             requirement: .viewer)) { invocation in
                guard let viewer = invocation.viewer else { return }
                SelfTest.runAndLog(in: viewer)
            }
        }
        if selfTest {
            // Leva a série ao corte do meio, para as capturas do teste automático mostrarem imagem.
            try context.register(IsiXCommand(id: Command.selfTestMiddle, title: "NeuroLaudo: corte do meio", placement: .other,
                                             requirement: .viewer)) { invocation in
                guard let viewer = invocation.viewer else { return }
                let count = try viewer.series().sliceCount
                try viewer.setCurrentSlice(count / 2)
                PluginLog.note("autoteste: corte \(count / 2 + 1) de \(count)")
            }
        }
        // Prova de que o IsiX carregou e ativou o complemento; ver PluginLog.
        let count = NeuroWindowPresets.ct.count + 9 + (selfTest ? 2 : 0)
        PluginLog.note("NeuroLaudo \(context.info.version) ativado, \(count) comandos")
    }

    public func deactivate() {
        keyObservation?.invalidate()
        keyObservation = nil
        eventObservation?.invalidate()
        eventObservation = nil
        autoOpen = nil
        volumetryTask?.cancel()
        volumetryTask = nil
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
                ? "Ligada: o exame que chegar pela rede abre arrumado pelo protocolo de neuro, se o IsiX ainda não o tiver aberto."
                : "Desligada: os exames chegam ao banco de dados e não abrem sozinhos."
            self.presenter?.show(MeasureOutcome(title: "Abertura automática", text: text), in: invocation.parentWindow)
        }
        // O exame que chega (por exemplo, pelo botão do PACS) abre sozinho.
        eventObservation = try context.observe([.imagesAdded]) { [weak self] event in
            guard let self, let context = self.context else { return }
            self.autoOpen?.handle(event, context: context)
        }
    }

    // MARK: volumetria

    /// Começa a volumetria da série aberta e devolve a tarefa em segundo plano.
    @discardableResult
    func startVolumetry(in viewer: IsiXViewer, context: IsiXPluginContext) throws -> IsiXTask {
        if let running = volumetryTask, !running.isFinished {
            throw PluginFailure("Já há uma volumetria em andamento. Aguarde o resultado.")
        }
        let engine: any VolumetryEngine = self.engine ?? ProcessEngine.standard()
        try engine.checkInstalled()
        let job = try Volumetry.prepare(viewer: viewer, context: context)
        PluginLog.note("volumetria: série copiada, \(job.geometries.count) cortes, orientação \(job.orientation)")
        // O que fazer na janela quando o motor terminar. Fica na linha principal, como os outros comandos.
        let finish: @MainActor @Sendable (MeasureOutcome, VolumetryStored?) -> Void = { [weak self] outcome, stored in
            self?.finishVolumetry(outcome, stored: stored, context: context)
        }
        let task = try context.startTask(named: "Volumetria cerebral") { progress in
            let done = await Volumetry.perform(job, engine: engine, context: context, progress: progress)
            await finish(done.outcome, done.stored)
        }
        volumetryTask = task
        return task
    }

    private func finishVolumetry(_ outcome: MeasureOutcome, stored: VolumetryStored?, context: IsiXPluginContext) {
        if let stored {
            PluginLog.note("volumetria: concluída, relatório \(stored.reportSeriesUID ?? "-"), mapa \(stored.mapSeriesUID ?? "-")")
            // Abre o mapa colorido ao lado do T1. O IsiX já o posiciona no mesmo corte em que o T1 está.
            if let map = stored.mapSeriesUID { _ = try? context.database().openViewer(forSeries: map) }
        } else {
            PluginLog.note("volumetria: não concluída. \(outcome.text.prefix(300))")
        }
        presenter?.show(outcome, in: nil)
    }

    // MARK: apoio

    static func describe(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? String(describing: error)
    }
}
