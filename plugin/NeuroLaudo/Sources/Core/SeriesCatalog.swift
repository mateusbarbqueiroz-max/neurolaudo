//  NeuroLaudo — cálculo puro, sem dependência do IsiX nem do AppKit.
//
//  Lista dos nomes de exame e de série que aparecem no banco, com quantas vezes
//  cada um aparece e como o NeuroLaudo o reconhece. Serve para ensinar ao
//  programa os nomes de um serviço: a lista é copiada e mandada a quem mantém o
//  NeuroLaudo. Só entram nomes de exame e de série, nunca dados de paciente.

import Foundation

/// Uma série do banco, só com o que a lista usa.
struct CatalogEntry: Equatable, Sendable {
    var modality: String
    var studyDescription: String
    var seriesDescription: String
}

enum SeriesCatalog {
    /// Modalidades listadas, na ordem em que aparecem no texto.
    static let modalities: [(code: String, title: String)] = [("MR", "RM"), ("CT", "TC")]

    /// Nomes iguais a menos de espaços e caixa contam juntos; vale a grafia mais frequente.
    private static func key(_ text: String) -> String {
        text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            .split(whereSeparator: \.isWhitespace).joined(separator: " ")
    }

    /// Conta os nomes, do mais frequente ao menos frequente; empate em ordem alfabética.
    static func counts(_ names: [String]) -> [(name: String, count: Int)] {
        var total: [String: Int] = [:]
        var spellings: [String: [String: Int]] = [:]
        for raw in names {
            let name = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !name.isEmpty else { continue }
            let k = key(name)
            total[k, default: 0] += 1
            spellings[k, default: [:]][name, default: 0] += 1
        }
        return total.map { k, count -> (name: String, count: Int) in
            let best = spellings[k]!.max { a, b in a.value < b.value || (a.value == b.value && a.key > b.key) }!.key
            return (best, count)
        }
        .sorted { $0.count != $1.count ? $0.count > $1.count : $0.name.lowercased() < $1.name.lowercased() }
    }

    /// O texto pronto para copiar. `studyCounts`: quantos exames de cada modalidade foram lidos.
    static func report(_ entries: [CatalogEntry], studyCounts: [String: Int], limitPerModality: Int) -> String {
        var lines = ["Nomes das séries no banco do IsiX",
                     "Só nomes de exame e de série, sem dados de paciente. Confira antes de mandar."]
        let read = modalities.map { "\(studyCounts[$0.code] ?? 0) de \($0.title)" }.joined(separator: " e ")
        lines.append("Exames lidos: \(read) (os mais recentes, até \(limitPerModality) de cada).")
        for (code, title) in modalities {
            let mine = entries.filter { $0.modality.uppercased() == code }
            lines.append("")
            lines.append(title)
            guard !mine.isEmpty else {
                lines.append("  nenhuma série de \(title) no banco")
                continue
            }
            let studies = counts(mine.map(\.studyDescription))
            if !studies.isEmpty {
                lines.append("Nomes de exame: " + studies.map { "\($0.name) (\($0.count))" }.joined(separator: " · "))
            }
            lines.append("Séries (vezes) → como o NeuroLaudo reconhece hoje:")
            for item in counts(mine.map(\.seriesDescription)) {
                let kind = SeriesClassifier.classify(description: item.name, modality: code)
                let label = kind == .other ? "não reconhecida" : kind.label
                lines.append("  \(item.name) (\(item.count)) → \(label)")
            }
        }
        return lines.joined(separator: "\n")
    }
}
