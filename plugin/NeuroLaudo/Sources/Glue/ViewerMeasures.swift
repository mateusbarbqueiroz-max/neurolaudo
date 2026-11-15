//  NeuroLaudo — lê as medidas que o usuário desenhou no visualizador e entrega
//  ao núcleo de cálculo. Sem interface: o resultado é texto, mostrado por quem chama.

import Foundation
import IsiXPluginKit

/// O resultado de um comando, pronto para mostrar e para colar no laudo.
struct MeasureOutcome: Equatable, Sendable {
    var title: String
    var text: String
}

extension Vec3 {
    init(_ v: IsiXVector3) {
        self.init(x: v.x, y: v.y, z: v.z)
    }
}

/// Uma linha de medida do visualizador e seu segmento em coordenadas do paciente.
struct MeasuredLine: Sendable {
    var roi: IsiXROI
    var segment: Segment
}

/// Os dados que o ABC/2 lê da imagem; o número de cortes vem do usuário.
struct HematomaInputs: Sendable {
    var first: MeasuredLine
    var second: MeasuredLine
    var sliceIntervalMM: Double
}

@MainActor enum ViewerMeasures {
    /// As linhas de medida do corte atual.
    static func lines(in viewer: IsiXViewer) throws -> [MeasuredLine] {
        let geometry = try viewer.geometry()
        return try viewer.rois().compactMap { roi in
            guard roi.kind == .line else { return nil }
            let ends = endpoints(of: roi, geometry: geometry)
            guard ends.count >= 2, let first = ends.first, let last = ends.last else { return nil }
            return MeasuredLine(roi: roi, segment: Segment(start: first, end: last))
        }
    }

    /// Os pontos (ROI de ponto) do corte atual.
    static func points(in viewer: IsiXViewer) throws -> [(roi: IsiXROI, point: Vec3)] {
        let geometry = try viewer.geometry()
        return try viewer.rois().compactMap { roi in
            guard roi.kind == .point, let point = endpoints(of: roi, geometry: geometry).first else { return nil }
            return (roi, point)
        }
    }

    /// Coordenadas do paciente de uma ROI; se o visualizador não as deu, calcula
    /// pelos pixels e pela geometria da imagem.
    private static func endpoints(of roi: IsiXROI, geometry: IsiXImageGeometry) -> [Vec3] {
        if roi.patientPoints.count == roi.points.count, !roi.patientPoints.isEmpty {
            return roi.patientPoints.map(Vec3.init)
        }
        return roi.points.map { Vec3(geometry.patientPoint(of: $0)) }
    }

    /// As duas linhas que valem: as duas selecionadas, se houver exatamente duas
    /// selecionadas; senão, as duas únicas do corte.
    static func twoLines(in viewer: IsiXViewer) throws -> (MeasuredLine, MeasuredLine) {
        let all = try lines(in: viewer)
        let selected = all.filter(\.roi.isSelected)
        if selected.count == 2 { return (selected[0], selected[1]) }
        guard all.count == 2 else { throw MeasureError.needsTwoLines(found: all.count) }
        return (all[0], all[1])
    }

    private static func rename(_ roi: IsiXROI, to name: String, in viewer: IsiXViewer) {
        // Rotular a medida na imagem é um extra: se falhar, o resultado continua valendo.
        _ = try? viewer.updateROI(roi.id, IsiXROIUpdate(name: name))
    }

    // MARK: Índice de Evans

    static func evans(in viewer: IsiXViewer) throws -> MeasureOutcome {
        let (a, b) = try twoLines(in: viewer)
        let result = try NeuroMeasures.evans(a.segment, b.segment)
        let horns = a.segment.lengthMM <= b.segment.lengthMM ? a : b
        let skull = a.segment.lengthMM <= b.segment.lengthMM ? b : a
        rename(horns.roi, to: "Cornos frontais", in: viewer)
        rename(skull.roi, to: "Crânio (interno)", in: viewer)
        return MeasureOutcome(title: "Índice de Evans", text: result.summary)
    }

    // MARK: Desvio da linha média

    /// Uma linha sobre a linha média ideal e um ponto no septo pelúcido. Sem
    /// ponto, vale uma segunda linha: a mais longa é a linha média, e o septo é
    /// a ponta da outra que fica mais longe dela.
    static func midlineShift(in viewer: IsiXViewer) throws -> MeasureOutcome {
        let all = try lines(in: viewer)
        let marks = try points(in: viewer)
        guard let longest = all.max(by: { $0.segment.lengthMM < $1.segment.lengthMM }) else {
            throw MeasureError.needsLineAndPoint
        }
        let septum: Vec3
        if marks.count == 1 {
            septum = marks[0].point
            rename(marks[0].roi, to: "Septo pelúcido", in: viewer)
        } else if marks.isEmpty, all.count == 2, let other = all.first(where: { $0.roi.id != longest.roi.id }) {
            let d1 = Geometry.pointToLine(other.segment.start, through: longest.segment.start, and: longest.segment.end)?.distance ?? 0
            let d2 = Geometry.pointToLine(other.segment.end, through: longest.segment.start, and: longest.segment.end)?.distance ?? 0
            septum = d1 >= d2 ? other.segment.start : other.segment.end
            rename(other.roi, to: "Septo pelúcido", in: viewer)
        } else {
            throw MeasureError.needsLineAndPoint
        }
        rename(longest.roi, to: "Linha média", in: viewer)
        let result = try NeuroMeasures.midlineShift(midline: longest.segment, septum: septum)
        return MeasureOutcome(title: "Desvio da linha média", text: result.summary)
    }

    // MARK: Volume de hematoma (ABC/2)

    static func hematomaInputs(in viewer: IsiXViewer) throws -> HematomaInputs {
        let (a, b) = try twoLines(in: viewer)
        let geometry = try viewer.geometry()
        let interval = abs(geometry.sliceInterval) > 1e-6 ? abs(geometry.sliceInterval) : abs(geometry.sliceThickness)
        return HematomaInputs(first: a, second: b, sliceIntervalMM: interval)
    }

    static func hematoma(_ inputs: HematomaInputs, sliceCount: Double, in viewer: IsiXViewer?) throws -> MeasureOutcome {
        let result = try NeuroMeasures.hematoma(inputs.first.segment, inputs.second.segment, sliceCount: sliceCount,
                                                sliceIntervalMM: inputs.sliceIntervalMM)
        if let viewer, viewer.isOpen {
            let aIsFirst = inputs.first.segment.lengthMM >= inputs.second.segment.lengthMM
            rename(aIsFirst ? inputs.first.roi : inputs.second.roi, to: "Hematoma A", in: viewer)
            rename(aIsFirst ? inputs.second.roi : inputs.first.roi, to: "Hematoma B", in: viewer)
        }
        return MeasureOutcome(title: "Volume de hematoma (ABC/2)", text: result.summary)
    }
}
