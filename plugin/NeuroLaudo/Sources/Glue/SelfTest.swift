//  NeuroLaudo — autoteste das medidas dentro do IsiX de verdade.
//
//  Desenha, pelo kit, linhas e um ponto de tamanho conhecido na imagem aberta,
//  lê tudo de volta pelo mesmo caminho dos comandos de medida e compara com o
//  esperado. Apaga o que desenhou. Serve ao teste automático no servidor Mac:
//  o comando só existe quando o IsiX é aberto com `-NeuroLaudoAutoteste YES`.

import Foundation
import IsiXPluginKit

@MainActor enum SelfTest {
    static let settingsKey = "NeuroLaudoAutoteste"

    struct Check: Equatable, Sendable {
        var name: String
        var passed: Bool
        var detail: String

        var line: String { "autoteste \(name): \(passed ? "ok" : "FALHOU") (\(detail))" }
    }

    private static func near(_ value: Double?, _ expected: Double, tolerance: Double = 0.2) -> Bool {
        guard let value else { return false }
        return abs(value - expected) <= tolerance
    }

    private static func text(_ value: Double?) -> String {
        value.map { Fmt.number($0, decimals: 2) } ?? "sem valor"
    }

    /// Roda as conferências na imagem atual do visualizador.
    static func run(in viewer: IsiXViewer) throws -> [Check] {
        let geometry = try viewer.geometry()
        guard geometry.columnSpacing > 0, geometry.rowSpacing > 0 else {
            throw PluginFailure("Esta imagem não tem espaçamento de pixel; o autoteste precisa dele.")
        }
        var checks: [Check] = []
        var created: [IsiXROIID] = []

        // Posições dadas em milímetros a partir do canto da imagem.
        func pixel(_ xMM: Double, _ yMM: Double) -> IsiXPixelPoint {
            IsiXPixelPoint(x: xMM / geometry.columnSpacing, y: yMM / geometry.rowSpacing)
        }
        func addLine(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) throws -> IsiXROI {
            let roi = try viewer.addROI(IsiXROIDraft(kind: .line, points: [pixel(x0, y0), pixel(x1, y1)], name: "autoteste"))
            created.append(roi.id)
            return roi
        }
        func clear() {
            for id in created { try? viewer.removeROI(id) }
            created.removeAll()
        }
        defer { clear() }

        // 1. Uma linha de 120 mm: o nosso comprimento e o que o próprio IsiX mede.
        let skull = try addLine(20, 60, 140, 60)
        let ours = try ViewerMeasures.lines(in: viewer).first { $0.roi.id == skull.id }?.segment.lengthMM
        let theirs = try viewer.statistics(of: skull.id).length
        checks.append(Check(name: "comprimento", passed: near(ours, 120) && near(theirs, 120),
                            detail: "NeuroLaudo \(text(ours)) mm, IsiX \(text(theirs)) mm, esperado 120,00"))

        // 2. Índice de Evans: 42 mm sobre 120 mm = 0,35.
        _ = try addLine(50, 40, 92, 40)
        let (first, second) = try ViewerMeasures.twoLines(in: viewer)
        let evans = try NeuroMeasures.evans(first.segment, second.segment)
        checks.append(Check(name: "Evans", passed: near(evans.index, 0.35, tolerance: 0.005),
                            detail: "índice \(text(evans.index)), esperado 0,35"))
        clear()

        // 3. Desvio da linha média: ponto a 6 mm da linha; a medida também rotula as marcas.
        _ = try addLine(100, 20, 100, 180)
        let point = try viewer.addROI(IsiXROIDraft(kind: .point, points: [pixel(106, 100)], name: "autoteste"))
        created.append(point.id)
        let midline = try ViewerMeasures.midlineShift(in: viewer)
        let labelled = try viewer.rois().contains { $0.name == "Linha média" }
        checks.append(Check(name: "linha média", passed: midline.text.contains("6,0 mm") && labelled,
                            detail: midline.text + (labelled ? "" : " [marcas não rotuladas]")))
        clear()

        // 4. ABC/2: 40 x 30 mm perpendiculares, quatro cortes.
        _ = try addLine(80, 100, 120, 100)
        _ = try addLine(100, 85, 100, 115)
        let inputs = try ViewerMeasures.hematomaInputs(in: viewer)
        let hematoma = try NeuroMeasures.hematoma(inputs.first.segment, inputs.second.segment, sliceCount: 4,
                                                  sliceIntervalMM: inputs.sliceIntervalMM)
        let expected = 40.0 * 30.0 * (4 * inputs.sliceIntervalMM) / 2000
        checks.append(Check(name: "ABC/2", passed: near(hematoma.volumeML, expected, tolerance: 0.05) && hematoma.isRoughlyPerpendicular,
                            detail: "volume \(text(hematoma.volumeML)) mL, esperado \(text(expected)); "
                                + "intervalo entre cortes \(text(inputs.sliceIntervalMM)) mm"))
        clear()

        // 5. Janela: aplicar e ler de volta, depois devolver a que estava.
        let before = try viewer.windowLevel()
        try viewer.setWindowLevel(IsiXWindowLevel(center: 600, width: 2800))
        let after = try viewer.windowLevel()
        try viewer.setWindowLevel(before)
        checks.append(Check(name: "janela", passed: near(after.center, 600, tolerance: 1) && near(after.width, 2800, tolerance: 1),
                            detail: "lida \(text(after.center))/\(text(after.width)), esperado 600/2800"))

        return checks
    }

    /// Roda e escreve o resultado no log do macOS. Devolve quantas conferências passaram.
    @discardableResult
    static func runAndLog(in viewer: IsiXViewer) -> (passed: Int, total: Int) {
        do {
            let checks = try run(in: viewer)
            for check in checks { PluginLog.note(check.line) }
            let passed = checks.filter(\.passed).count
            PluginLog.note("autoteste: \(passed) de \(checks.count) conferências passaram")
            return (passed, checks.count)
        } catch {
            PluginLog.note("autoteste interrompido: \(NeuroLaudoPlugin.describe(error))")
            return (0, 0)
        }
    }
}
