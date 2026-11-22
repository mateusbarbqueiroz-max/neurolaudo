//  NeuroLaudo — texto para o laudo: junta, por exame, a última frase de cada medida.
//
//  O usuário lauda por ditado no Laudite, com máscaras e frases prontas próprias; este
//  texto é para colar nelas. Formato provisório (as frases de cada comando, uma por linha),
//  até chegarem as máscaras do usuário.

import Foundation

/// Uma frase para o laudo e, se houver, um aviso para quem mediu, que fica fora do texto copiado.
struct ReportEntry: Equatable, Sendable {
    /// A ordem dos tipos é a ordem das frases no texto.
    enum Kind: Int, CaseIterable, Comparable, Sendable {
        case midline, hematoma, aspects, evans, volumetry

        static func < (lhs: Kind, rhs: Kind) -> Bool { lhs.rawValue < rhs.rawValue }
    }

    var kind: Kind
    var sentence: String
    var warning: String? = nil
}

/// As frases de um exame: a última de cada tipo. Medir de novo troca a frase anterior.
struct ReportBook: Equatable, Sendable {
    private(set) var entries: [ReportEntry.Kind: ReportEntry] = [:]

    var isEmpty: Bool { entries.isEmpty }
    var ordered: [ReportEntry] { entries.values.sorted { $0.kind < $1.kind } }
    /// O texto para colar: uma frase por linha, na ordem dos tipos.
    var text: String { ordered.map(\.sentence).joined(separator: "\n") }
    var warnings: [String] { ordered.compactMap(\.warning) }

    mutating func record(_ entry: ReportEntry) { entries[entry.kind] = entry }
    mutating func remove(_ kind: ReportEntry.Kind) { entries[kind] = nil }
}

/// As frases de vários exames, só na memória enquanto o IsiX está aberto: nada vai para o disco.
/// Guarda os exames usados por último, até `capacity`.
struct ReportStore: Sendable {
    static let capacity = 30

    private var books: [String: ReportBook] = [:]
    /// Exames do usado há mais tempo ao usado por último.
    private(set) var recent: [String] = []

    var lastStudy: String? { recent.last }

    func book(for study: String) -> ReportBook? { books[study] }

    mutating func record(_ entry: ReportEntry, study: String) {
        books[study, default: ReportBook()].record(entry)
        recent.removeAll { $0 == study }
        recent.append(study)
        while recent.count > Self.capacity { books[recent.removeFirst()] = nil }
    }

    mutating func remove(_ kind: ReportEntry.Kind, study: String) {
        books[study]?.remove(kind)
        if books[study]?.isEmpty == true {
            books[study] = nil
            recent.removeAll { $0 == study }
        }
    }
}
