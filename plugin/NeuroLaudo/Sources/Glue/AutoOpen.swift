//  NeuroLaudo — abre sozinho o exame que chega, já arrumado pelo protocolo de neuro.
//
//  Quando um recebimento termina e trouxe um único exame, o exame é aberto pelo
//  protocolo de neuro, a menos que algo dele já esteja aberto.
//
//  O botão do PACS pede "busque este exame e depois abra" (then=Open). Até a
//  versão 6.0.3 o IsiX buscava e não abria, e era este arquivo que abria. Desde
//  a 6.0.4 o próprio IsiX abre o exame assim que chega a primeira série (e
//  confere a chegada a cada meio segundo). Para não empilhar janelas enquanto o
//  médico já lê, o complemento espera alguns segundos depois do fim do
//  recebimento e não faz nada se o IsiX já abriu o exame. Exames que chegam
//  sem link (enviados pelo PACS, por exemplo) continuam abrindo pelo complemento.

import Foundation
import IsiXPluginKit

/// Onde o complemento guarda suas opções. Em macOS, as preferências do IsiX.
@MainActor protocol SettingsStore: AnyObject {
    func bool(forKey key: String) -> Bool?
    func set(_ value: Bool, forKey key: String)
}

@MainActor final class DefaultsStore: SettingsStore {
    func bool(forKey key: String) -> Bool? {
        UserDefaults.standard.object(forKey: key) == nil ? nil : UserDefaults.standard.bool(forKey: key)
    }

    func set(_ value: Bool, forKey key: String) {
        UserDefaults.standard.set(value, forKey: key)
    }
}

@MainActor final class MemoryStore: SettingsStore {
    private var values: [String: Bool] = [:]
    func bool(forKey key: String) -> Bool? { values[key] }
    func set(_ value: Bool, forKey key: String) { values[key] = value }
}

@MainActor final class AutoOpen {
    static let settingsKey = "NeuroLaudoAbrirAoChegar"
    /// Segundos de espera depois do fim do recebimento, para o IsiX abrir antes, se for abrir.
    static let defaultDelay: TimeInterval = 3

    private let store: SettingsStore
    let delay: TimeInterval

    init(store: SettingsStore, delay: TimeInterval = AutoOpen.defaultDelay) {
        self.store = store
        self.delay = delay
    }

    /// Ligado até o usuário desligar.
    var isEnabled: Bool {
        get { store.bool(forKey: Self.settingsKey) ?? true }
        set { store.set(newValue, forKey: Self.settingsKey) }
    }

    /// O exame a abrir depois de um recebimento, ou `nil`.
    ///
    /// Só quando o recebimento terminou e trouxe um único exame. Se o IsiX
    /// informou quais imagens vieram pela rede, só essas contam: arquivos
    /// importados à mão no mesmo momento não disparam a abertura.
    static func studyToOpen(after added: IsiXImagesAdded) -> String? {
        guard added.isComplete else { return nil }
        let fromNetwork = Set(added.sopInstanceUIDsByCallingAETitle.values.joined())
        let images = fromNetwork.isEmpty ? added.images : added.images.filter { fromNetwork.contains($0.sopInstanceUID) }
        let studies = Set(images.map(\.studyInstanceUID))
        return studies.count == 1 ? studies.first : nil
    }

    /// Trata um evento do IsiX. Sem espera, abre na hora e devolve os nomes das séries abertas;
    /// com espera, agenda a abertura e devolve uma lista vazia.
    @discardableResult
    func handle(_ event: IsiXEvent, context: IsiXPluginContext) -> [String] {
        guard isEnabled, case .imagesAdded(let added) = event, let studyUID = Self.studyToOpen(after: added) else { return [] }
        guard delay > 0 else { return open(studyUID, context: context) }
        let nanoseconds = UInt64(delay * 1_000_000_000)
        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: nanoseconds)
            self?.open(studyUID, context: context)
        }
        return []
    }

    /// Abre o exame pelo protocolo de neuro, a menos que algo dele já esteja aberto.
    @discardableResult
    func open(_ studyUID: String, context: IsiXPluginContext) -> [String] {
        guard isEnabled else { return [] }
        if Self.isOpen(studyUID, context: context) {
            PluginLog.note("exame recebido já estava aberto (pelo IsiX); nada aberto pelo complemento")
            return []
        }
        do {
            let opened = try ProtocolCommands.openArrived(studyUID: studyUID, context: context)
            if !opened.isEmpty { PluginLog.note("exame recebido aberto: \(opened.count) série(s)") }
            return opened
        } catch {
            PluginLog.note("exame recebido não pôde ser aberto: \(NeuroLaudoPlugin.describe(error))")
            return []
        }
    }

    /// Há alguma janela aberta com uma série deste exame?
    static func isOpen(_ studyUID: String, context: IsiXPluginContext) -> Bool {
        let viewers = (try? context.openViewers()) ?? []
        return viewers.contains { (try? $0.series().studyInstanceUID) == studyUID }
    }
}
