//  NeuroLaudo — ASPECTS (Alberta Stroke Program Early CT Score).

import Foundation

struct AspectsRegion: Equatable, Sendable {
    var code: String
    var name: String
}

enum BrainSide: String, CaseIterable, Sendable {
    case right = "direita"
    case left = "esquerda"
}

enum Aspects {
    /// As dez regiões do território da artéria cerebral média.
    static let regions: [AspectsRegion] = [
        AspectsRegion(code: "C", name: "Caudado"),
        AspectsRegion(code: "L", name: "Núcleo lentiforme"),
        AspectsRegion(code: "IC", name: "Cápsula interna"),
        AspectsRegion(code: "I", name: "Ínsula"),
        AspectsRegion(code: "M1", name: "Córtex anterior da ACM"),
        AspectsRegion(code: "M2", name: "Córtex lateral à ínsula"),
        AspectsRegion(code: "M3", name: "Córtex posterior da ACM"),
        AspectsRegion(code: "M4", name: "Córtex anterior, supraganglionar"),
        AspectsRegion(code: "M5", name: "Córtex lateral, supraganglionar"),
        AspectsRegion(code: "M6", name: "Córtex posterior, supraganglionar"),
    ]

    /// 10 menos um ponto por região com sinais de isquemia precoce.
    static func score(affected: Set<String>) throws -> Int {
        let valid = Set(regions.map(\.code))
        let unknown = affected.subtracting(valid)
        guard unknown.isEmpty else {
            throw MeasureError.invalidValue("região de ASPECTS desconhecida: \(unknown.sorted().joined(separator: ", "))")
        }
        return 10 - affected.count
    }

    /// Frase pronta para o laudo.
    static func summary(affected: Set<String>, side: BrainSide) throws -> String {
        let value = try score(affected: affected)
        let territory = "território da artéria cerebral média \(side.rawValue)"
        guard !affected.isEmpty else {
            return "ASPECTS 10 no \(territory) (sem sinais de isquemia precoce)."
        }
        let ordered = regions.map(\.code).filter(affected.contains)
        return "ASPECTS \(value) no \(territory) (acometimento de: \(ordered.joined(separator: ", ")))."
    }
}
