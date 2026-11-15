//  NeuroLaudo — janelas (window level) de neurorradiologia para TC.

import Foundation

struct WindowPreset: Equatable, Sendable {
    /// Identificador estável do comando; não muda entre versões.
    var id: String
    var name: String
    /// Centro (nível) e largura em unidades Hounsfield.
    var center: Double
    var width: Double
    /// Dígito do atalho ⌃⌥+dígito sobre a imagem.
    var digit: Int

    var title: String {
        "Janela: \(name) (\(Fmt.number(center, decimals: 0))/\(Fmt.number(width, decimals: 0)))"
    }
}

enum NeuroWindowPresets {
    /// Valores iniciais, para o usuário ajustar ao seu gosto.
    static let ct: [WindowPreset] = [
        WindowPreset(id: "janela-encefalo", name: "Encéfalo", center: 40, width: 80, digit: 1),
        WindowPreset(id: "janela-avc", name: "AVC", center: 40, width: 40, digit: 2),
        WindowPreset(id: "janela-subdural", name: "Subdural", center: 75, width: 215, digit: 3),
        WindowPreset(id: "janela-osso", name: "Osso", center: 600, width: 2800, digit: 4),
        WindowPreset(id: "janela-angio", name: "Angio-TC", center: 200, width: 700, digit: 5),
        WindowPreset(id: "janela-partes-moles", name: "Partes moles", center: 50, width: 350, digit: 6),
    ]

    static func preset(forDigit digit: Int) -> WindowPreset? {
        ct.first { $0.digit == digit }
    }
}
