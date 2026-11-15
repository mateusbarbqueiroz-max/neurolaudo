//  NeuroLaudo — protocolos de exibição: quais séries abrir e em que ordem.
//  Também escolhe o exame anterior e a série correspondente para comparação.

import Foundation

/// Uma posição do protocolo: aceita os tipos listados, na ordem de preferência.
struct ProtocolSlot: Equatable, Sendable {
    var label: String
    var kinds: [SequenceKind]
}

struct NeuroProtocol: Equatable, Sendable {
    var id: String
    var title: String
    var modality: String
    var slots: [ProtocolSlot]
}

struct ProtocolSelection: Equatable, Sendable {
    /// Séries a abrir, na ordem do protocolo.
    var series: [SeriesInfo]
    /// Posições para as quais não houve série.
    var missing: [String]
}

struct StudyInfo: Equatable, Sendable {
    var uid: String
    var date: Date?
    var modalities: [String]
    var description: String?
}

enum NeuroProtocols {
    static let mrBrain = NeuroProtocol(
        id: "protocolo-rm-encefalo", title: "Protocolo: RM de encéfalo", modality: "MR",
        slots: [
            ProtocolSlot(label: "FLAIR", kinds: [.flair]),
            ProtocolSlot(label: "difusão", kinds: [.dwi]),
            ProtocolSlot(label: "ADC", kinds: [.adc]),
            ProtocolSlot(label: "SWI ou T2*", kinds: [.swi, .t2Star]),
            ProtocolSlot(label: "T1", kinds: [.t1]),
            ProtocolSlot(label: "T1 pós-contraste", kinds: [.t1Contrast]),
        ])

    static let ctHead = NeuroProtocol(
        id: "protocolo-tc-cranio", title: "Protocolo: TC de crânio", modality: "CT",
        slots: [
            ProtocolSlot(label: "parênquima", kinds: [.ctBrain]),
            ProtocolSlot(label: "osso", kinds: [.ctBone]),
            ProtocolSlot(label: "angio-TC", kinds: [.cta]),
        ])

    static let all: [NeuroProtocol] = [mrBrain, ctHead]

    /// Pontuação de uma série para ocupar uma posição: maior é melhor.
    private static func rank(_ s: SeriesInfo, kindIndex: Int) -> (Int, Int, Int, Int) {
        // 1º o tipo preferido da posição; 2º plano axial; 3º mais imagens; 4º número de série menor.
        (-kindIndex, SeriesClassifier.looksAxial(s.description) ? 1 : 0, min(s.imageCount, 10_000), -(s.seriesNumber ?? 0))
    }

    /// Para cada posição do protocolo, a melhor série ainda não usada.
    static func select(_ proto: NeuroProtocol, from series: [SeriesInfo]) -> ProtocolSelection {
        var remaining = series.filter { $0.modality.uppercased() == proto.modality && $0.imageCount > 0 }
        var chosen: [SeriesInfo] = []
        var missing: [String] = []
        for slot in proto.slots {
            var best: (index: Int, rank: (Int, Int, Int, Int))?
            for (i, s) in remaining.enumerated() {
                guard let kindIndex = slot.kinds.firstIndex(of: SeriesClassifier.classify(s)) else { continue }
                let r = rank(s, kindIndex: kindIndex)
                if best == nil || r > best!.rank { best = (i, r) }
            }
            if let best {
                chosen.append(remaining.remove(at: best.index))
            } else {
                missing.append(slot.label)
            }
        }
        return ProtocolSelection(series: chosen, missing: missing)
    }

    /// O protocolo que serve para um estudo com estas modalidades.
    static func protocolFor(modalities: [String]) -> NeuroProtocol? {
        let upper = Set(modalities.map { $0.uppercased() })
        return all.first { upper.contains($0.modality) }
    }
}

enum PriorStudies {
    /// O exame mais recente antes do atual que compartilha uma modalidade.
    static func previous(of current: StudyInfo, among all: [StudyInfo]) -> StudyInfo? {
        guard let currentDate = current.date else { return nil }
        let wanted = Set(current.modalities.map { $0.uppercased() })
        return all
            .filter { $0.uid != current.uid }
            .filter { study in
                guard let date = study.date, date < currentDate else { return false }
                return wanted.isEmpty || !wanted.isDisjoint(with: study.modalities.map { $0.uppercased() })
            }
            .max { ($0.date ?? .distantPast) < ($1.date ?? .distantPast) }
    }

    /// A série do exame anterior que corresponde à série atual: mesmo tipo e, de
    /// preferência, mesmo nome.
    static func counterpart(of current: SeriesInfo, in prior: [SeriesInfo]) -> SeriesInfo? {
        let kind = SeriesClassifier.classify(current)
        let name = SeriesClassifier.normalize(current.description)
        let sameModality = prior.filter { $0.modality.uppercased() == current.modality.uppercased() && $0.imageCount > 0 }
        if let exact = sameModality.first(where: { SeriesClassifier.normalize($0.description) == name }) {
            return exact
        }
        guard kind != .other, kind != .localizer else { return nil }
        let sameKind = sameModality.filter { SeriesClassifier.classify($0) == kind }
        let currentAxial = SeriesClassifier.looksAxial(current.description)
        return sameKind.max { a, b in
            let ra = (SeriesClassifier.looksAxial(a.description) == currentAxial ? 1 : 0, min(a.imageCount, 10_000))
            let rb = (SeriesClassifier.looksAxial(b.description) == currentAxial ? 1 : 0, min(b.imageCount, 10_000))
            return ra < rb
        }
    }
}
