//  NeuroLaudo — o comando "Texto para o laudo": mostra as frases das medidas e da
//  volumetria do exame, para copiar e colar no Laudite. Sem interface: o resultado é texto.

import Foundation
import IsiXPluginKit

@MainActor enum ReportCommands {
    static let title = "Texto para o laudo"

    /// O exame de uma série aberta, se o IsiX souber dizer.
    static func study(of viewer: IsiXViewer?) -> String? {
        guard let viewer, viewer.isOpen else { return nil }
        return try? viewer.series().studyInstanceUID
    }

    /// O texto do exame `study`. Copiar leva só as frases; o resto é para conferir antes de colar.
    static func outcome(study: String?, store: ReportStore, database: IsiXDatabase?) -> MeasureOutcome {
        guard let study, let book = store.book(for: study), !book.isEmpty else {
            return MeasureOutcome(title: title, text: "Ainda não há medidas deste exame. Faça as medidas (menu Plugins › "
                + "ROI Tools) ou a volumetria e chame este comando de novo. Vale o que foi medido desde que o IsiX foi aberto.",
                copyText: "")
        }
        var notes: [String] = []
        if let label = examLabel(study, database: database) { notes.append("Exame: \(label).") }
        notes.append("Vale a última medida de cada tipo feita neste exame desde que o IsiX foi aberto; refaça uma "
            + "medida para trocá-la. Copiar leva só as frases acima.")
        if !book.warnings.isEmpty {
            notes.append("Antes de colar, confira:\n" + book.warnings.map { "• " + $0 }.joined(separator: "\n"))
        }
        return MeasureOutcome(title: title, text: book.text + "\n\n" + notes.joined(separator: "\n\n"), copyText: book.text)
    }

    /// Descrição e data do exame, para conferir que o texto é do exame certo. Sem dados do paciente.
    static func examLabel(_ study: String, database: IsiXDatabase?) -> String? {
        guard let database, let found = try? database.study(withInstanceUID: study) else { return nil }
        let description = (found.studyDescription ?? "").trimmingCharacters(in: .whitespaces)
        let parts = [description.isEmpty ? (found.modalities.isEmpty ? "" : found.modalities.joined(separator: "/")) : description,
                     found.studyDate.map { "de " + Fmt.date($0) } ?? ""].filter { !$0.isEmpty }
        return parts.isEmpty ? nil : parts.joined(separator: " ")
    }
}
