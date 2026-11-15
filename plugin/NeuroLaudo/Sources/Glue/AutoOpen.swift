//  NeuroLaudo — abre sozinho o exame que chega, já arrumado pelo protocolo de neuro.
//
//  O botão do PACS pede "busque este exame e depois abra" (then=Open). O IsiX
//  busca, mas não abre. Este arquivo supre a segunda metade: quando um
//  recebimento termina e trouxe um único exame, o exame é aberto.

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

    private let store: SettingsStore

    init(store: SettingsStore) {
        self.store = store
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

    /// Trata um evento do IsiX. Devolve os nomes das séries que abriu.
    @discardableResult
    func handle(_ event: IsiXEvent, context: IsiXPluginContext) -> [String] {
        guard isEnabled, case .imagesAdded(let added) = event, let studyUID = Self.studyToOpen(after: added) else { return [] }
        do {
            let opened = try ProtocolCommands.openArrived(studyUID: studyUID, context: context)
            if !opened.isEmpty { PluginLog.note("exame recebido aberto: \(opened.count) série(s)") }
            return opened
        } catch {
            PluginLog.note("exame recebido não pôde ser aberto: \(NeuroLaudoPlugin.describe(error))")
            return []
        }
    }
}
