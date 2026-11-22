//  NeuroLaudo — medidas de neurorradiologia a partir de comprimentos e pontos.
//  Cálculo puro; a leitura das ROIs do visualizador fica em Glue/.

import Foundation

/// Erros com uma frase que o usuário consegue seguir.
enum MeasureError: Error, Equatable {
    case needsTwoLines(found: Int)
    case needsLineAndPoint
    case degenerate
    case invalidValue(String)
}

extension MeasureError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .needsTwoLines(let found):
            return "Preciso de duas medidas de comprimento neste corte (encontrei \(found)). "
                + "Desenhe as duas linhas; se houver mais de duas, selecione as duas que valem."
        case .needsLineAndPoint:
            return "Preciso de uma linha sobre a linha média ideal e de um ponto (ou de uma segunda linha) "
                + "no septo pelúcido, neste corte."
        case .degenerate:
            return "Uma das medidas tem comprimento zero. Refaça a linha."
        case .invalidValue(let what):
            return "Valor inválido: \(what)."
        }
    }
}

/// Índice de Evans: maior largura dos cornos frontais dividida pelo maior
/// diâmetro interno do crânio, no mesmo corte axial. Acima de 0,30 sugere
/// ventriculomegalia.
struct EvansResult: Equatable, Sendable {
    static let threshold = 0.30

    var hornsMM: Double
    var skullMM: Double

    var index: Double { hornsMM / skullMM }
    var isEnlarged: Bool { index > Self.threshold }

    var summary: String {
        let verdict = isEnlarged ? "acima de 0,30 (sugere ventriculomegalia)" : "dentro do limite de 0,30"
        return "Índice de Evans: \(Fmt.number(index, decimals: 2)), \(verdict). "
            + "Cornos frontais \(Fmt.mm(hornsMM)); diâmetro interno do crânio \(Fmt.mm(skullMM))."
    }
}

/// Volume de hematoma pelo método ABC/2.
struct HematomaResult: Equatable, Sendable {
    var aMM: Double
    var bMM: Double
    var cMM: Double
    /// Ângulo agudo entre A e B, em graus; o método pede perpendiculares.
    var angleDegrees: Double?

    var volumeML: Double { NeuroMeasures.abc2VolumeML(aMM: aMM, bMM: bMM, cMM: cMM) }
    var isRoughlyPerpendicular: Bool { (angleDegrees ?? 90) >= 70 }

    /// A frase para o laudo.
    var sentence: String {
        "Hematoma medindo \(Fmt.number(aMM / 10, decimals: 1)) x \(Fmt.number(bMM / 10, decimals: 1)) x "
            + "\(Fmt.number(cMM / 10, decimals: 1)) cm, com volume estimado de \(Fmt.number(volumeML, decimals: 1)) mL (método ABC/2)."
    }

    /// Aviso para quem mediu; não vai para o laudo.
    var warning: String? {
        guard let angle = angleDegrees, !isRoughlyPerpendicular else { return nil }
        return "Atenção: A e B formam \(Fmt.number(angle, decimals: 0))°; o método pede medidas perpendiculares."
    }

    var summary: String { sentence + (warning.map { " " + $0 } ?? "") }
}

enum Side: String, Equatable, Sendable {
    case left = "para a esquerda"
    case right = "para a direita"
    case indeterminate = "sem lado definido"
}

/// Desvio da linha média: distância do septo pelúcido à linha média ideal.
struct MidlineShiftResult: Equatable, Sendable {
    var shiftMM: Double
    var side: Side

    var summary: String {
        if shiftMM < 0.5 { return "Sem desvio mensurável das estruturas da linha média." }
        return "Desvio das estruturas da linha média de \(Fmt.mm(shiftMM)) \(side.rawValue)."
    }
}

enum NeuroMeasures {
    /// A·B·C/2 com as três medidas em milímetros; resultado em mL (cm³).
    static func abc2VolumeML(aMM: Double, bMM: Double, cMM: Double) -> Double {
        (aMM / 10) * (bMM / 10) * (cMM / 10) / 2
    }

    /// Duas linhas no mesmo corte: a menor é a largura dos cornos frontais, a
    /// maior é o diâmetro interno do crânio.
    static func evans(_ first: Segment, _ second: Segment) throws -> EvansResult {
        let a = first.lengthMM, b = second.lengthMM
        guard a > 1e-6, b > 1e-6 else { throw MeasureError.degenerate }
        return EvansResult(hornsMM: min(a, b), skullMM: max(a, b))
    }

    /// Duas linhas no corte de maior hematoma (A = a maior, B = a menor) e a
    /// extensão craniocaudal C = número de cortes com hematoma × intervalo entre cortes.
    static func hematoma(_ first: Segment, _ second: Segment, sliceCount: Double, sliceIntervalMM: Double) throws -> HematomaResult {
        let l1 = first.lengthMM, l2 = second.lengthMM
        guard l1 > 1e-6, l2 > 1e-6 else { throw MeasureError.degenerate }
        guard sliceCount > 0 else { throw MeasureError.invalidValue("o número de cortes deve ser maior que zero") }
        guard sliceIntervalMM > 0 else { throw MeasureError.invalidValue("o intervalo entre cortes não está disponível nesta série") }
        return HematomaResult(aMM: max(l1, l2), bMM: min(l1, l2), cMM: sliceCount * sliceIntervalMM,
                              angleDegrees: Geometry.acuteAngle(first, second))
    }

    /// `midline`: linha entre as inserções anterior e posterior da foice.
    /// `septum`: ponto no septo pelúcido. O lado vem do eixo x do paciente (LPS:
    /// x cresce para a esquerda do paciente).
    static func midlineShift(midline: Segment, septum: Vec3) throws -> MidlineShiftResult {
        guard let (distance, foot) = Geometry.pointToLine(septum, through: midline.start, and: midline.end) else {
            throw MeasureError.degenerate
        }
        let dx = (septum - foot).x
        let side: Side
        if abs(dx) < 0.25 || abs(dx) < 0.5 * distance {
            side = .indeterminate
        } else {
            side = dx > 0 ? .left : .right
        }
        return MidlineShiftResult(shiftMM: distance, side: side)
    }
}
