//  NeuroLaudo — aplica as janelas de neuro ao visualizador.

#if canImport(AppKit)
import AppKit
#endif
import Foundation
import IsiXPluginKit

/// Um problema que o usuário consegue resolver, dito em uma frase.
struct PluginFailure: Error, LocalizedError, Equatable {
    var message: String

    init(_ message: String) {
        self.message = message
    }

    var errorDescription: String? { message }
}

@MainActor enum WindowCommands {
    /// Códigos das teclas da fileira de números, iguais nos teclados ANSI e ABNT2.
    /// Com ⌥ apertado o caractere muda, então a tecla é reconhecida pelo código.
    static let digitKeyCodes: [UInt16: Int] = [18: 1, 19: 2, 20: 3, 21: 4, 23: 5, 22: 6, 26: 7, 28: 8, 25: 9]

    static func apply(_ preset: WindowPreset, to viewer: IsiXViewer) throws {
        let modality = (try viewer.series().modality ?? "").uppercased()
        guard modality.isEmpty || modality == "CT" else {
            throw PluginFailure("As janelas de neuro valem para tomografia. Esta série é de \(modality).")
        }
        try viewer.setWindowLevel(IsiXWindowLevel(center: preset.center, width: preset.width))
    }

    /// O preset pedido por ⌃⌥ + dígito, se a tecla for essa.
    static func preset(forKeyCode keyCode: UInt16?, modifiers: NSEvent.ModifierFlags) -> WindowPreset? {
        guard modifiers.contains(.control), modifiers.contains(.option), !modifiers.contains(.command),
              let keyCode, let digit = digitKeyCodes[keyCode] else { return nil }
        return NeuroWindowPresets.preset(forDigit: digit)
    }
}
