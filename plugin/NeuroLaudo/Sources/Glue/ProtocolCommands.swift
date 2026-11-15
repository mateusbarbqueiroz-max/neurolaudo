//  NeuroLaudo — protocolos de exibição e comparação com o exame anterior:
//  escolhe as séries pelo núcleo e pede ao IsiX que as abra, na ordem.

import Foundation
import IsiXPluginKit

extension SeriesInfo {
    init(_ s: IsiXSeries) {
        self.init(uid: s.seriesInstanceUID, description: s.seriesDescription ?? "", modality: s.modality ?? "",
                  imageCount: s.imageCount, seriesNumber: s.seriesNumber)
    }
}

extension StudyInfo {
    init(_ s: IsiXStudy) {
        self.init(uid: s.studyInstanceUID, date: s.studyDate, modalities: s.modalities, description: s.studyDescription)
    }
}

@MainActor enum ProtocolCommands {
    /// O estudo do comando: o do visualizador da frente ou, sem visualizador, o
    /// selecionado na janela do banco de dados.
    static func targetStudyUID(viewer: IsiXViewer?, database: IsiXDatabase) throws -> String {
        if let viewer, viewer.isOpen, let uid = try viewer.series().studyInstanceUID, !uid.isEmpty {
            return uid
        }
        let selection = try database.selection()
        if let study = selection.studies.first { return study.studyInstanceUID }
        if let series = selection.series.first { return series.studyInstanceUID }
        throw PluginFailure("Selecione um exame na lista do banco de dados ou abra uma série dele.")
    }

    /// As séries que já estão abertas em algum visualizador.
    static func openSeriesUIDs(_ context: IsiXPluginContext) -> Set<String> {
        let viewers = (try? context.openViewers()) ?? []
        return Set(viewers.compactMap { try? $0.series().seriesInstanceUID })
    }

    /// Abre as séries do protocolo, na ordem. `proto` nulo escolhe pelo tipo do exame.
    static func apply(_ proto: NeuroProtocol?, context: IsiXPluginContext, viewer: IsiXViewer?) throws -> MeasureOutcome {
        let studyUID = try targetStudyUID(viewer: viewer, database: try context.database())
        return try apply(proto, context: context, studyUID: studyUID)
    }

    /// Modalidades que não são imagem para ler: laudos estruturados, marcações, registros.
    static let nonImageModalities: Set<String> = ["SR", "PR", "KO", "SEG", "DOC", "REG", "RTSTRUCT", "RTPLAN", "RTDOSE"]

    /// Abre um exame que acabou de chegar: pelo protocolo de neuro, se ele
    /// reconhecer o exame; senão, a primeira série de imagens, para que o exame
    /// abra de qualquer modo. Devolve os nomes das séries abertas.
    @discardableResult
    static func openArrived(studyUID: String, context: IsiXPluginContext) throws -> [String] {
        let database = try context.database()
        let before = openSeriesUIDs(context)
        if (try? apply(nil, context: context, studyUID: studyUID)) != nil {
            let opened = openSeriesUIDs(context).subtracting(before)
            return try database.series(inStudy: studyUID).filter { opened.contains($0.seriesInstanceUID) }
                .map { $0.seriesDescription ?? "" }
        }
        let series = try database.series(inStudy: studyUID)
        if series.contains(where: { before.contains($0.seriesInstanceUID) }) { return [] }
        let candidates = series
            .filter { $0.imageCount > 0 && !nonImageModalities.contains(($0.modality ?? "").uppercased()) }
            .sorted { ($0.seriesNumber ?? Int.max) < ($1.seriesNumber ?? Int.max) }
        guard let first = candidates.first else { return [] }
        try database.openViewer(forSeries: first.seriesInstanceUID)
        return [first.seriesDescription ?? ""]
    }

    /// Abre as séries do protocolo de um estudo, na ordem.
    static func apply(_ proto: NeuroProtocol?, context: IsiXPluginContext, studyUID: String) throws -> MeasureOutcome {
        let database = try context.database()
        let series = try database.series(inStudy: studyUID).map(SeriesInfo.init)
        let chosen: NeuroProtocol
        if let proto {
            chosen = proto
        } else if let guessed = NeuroProtocols.protocolFor(modalities: series.map(\.modality)) {
            chosen = guessed
        } else {
            throw PluginFailure("Este exame não é de RM nem de TC; não há protocolo de neuro para ele.")
        }
        let selection = NeuroProtocols.select(chosen, from: series)
        guard !selection.series.isEmpty else {
            throw PluginFailure("Não reconheci nenhuma série deste exame para o \(chosen.title). "
                + "Os nomes das séries deste serviço podem precisar ser ensinados ao NeuroLaudo.")
        }
        let alreadyOpen = openSeriesUIDs(context)
        var opened: [String] = []
        for item in selection.series where !alreadyOpen.contains(item.uid) {
            try database.openViewer(forSeries: item.uid)
            opened.append(item.description)
        }
        var text = opened.isEmpty ? "As séries do protocolo já estavam abertas."
            : "Séries abertas: " + opened.joined(separator: "; ") + "."
        if !selection.missing.isEmpty {
            text += " Não encontrei: " + selection.missing.joined(separator: ", ") + "."
        }
        return MeasureOutcome(title: chosen.title, text: text)
    }

    /// Abre, ao lado, a série equivalente do exame anterior do mesmo paciente.
    static func compareWithPrior(context: IsiXPluginContext, viewer: IsiXViewer?) throws -> MeasureOutcome {
        guard let viewer, viewer.isOpen else {
            throw PluginFailure("Abra a série que você quer comparar e repita o comando.")
        }
        let summary = try viewer.series()
        guard let studyUID = summary.studyInstanceUID, let seriesUID = summary.seriesInstanceUID else {
            throw PluginFailure("Esta janela não está ligada a um exame do banco de dados.")
        }
        let database = try context.database()
        guard let study = try database.study(withInstanceUID: studyUID) else {
            throw PluginFailure("Não encontrei este exame no banco de dados local.")
        }
        guard let patientID = study.patientID, !patientID.isEmpty else {
            throw PluginFailure("Este exame não tem identificação de paciente; não consigo procurar exames anteriores.")
        }
        let candidates = try database.studies(matching: IsiXStudyQuery(patientID: patientID)).map(StudyInfo.init)
        guard let prior = PriorStudies.previous(of: StudyInfo(study), among: candidates) else {
            throw PluginFailure("Não há exame anterior deste paciente, da mesma modalidade, no banco local. "
                + "Traga o exame anterior do PACS e repita o comando.")
        }
        let current = try database.series(withInstanceUID: seriesUID).map(SeriesInfo.init)
            ?? SeriesInfo(uid: seriesUID, description: summary.seriesDescription ?? "", modality: summary.modality ?? "",
                          imageCount: summary.sliceCount, seriesNumber: nil)
        let priorSeries = try database.series(inStudy: prior.uid).map(SeriesInfo.init)
        guard let match = PriorStudies.counterpart(of: current, in: priorSeries) else {
            throw PluginFailure("O exame anterior\(dateText(prior.date)) não tem série equivalente a «\(current.description)».")
        }
        if openSeriesUIDs(context).contains(match.uid) {
            return MeasureOutcome(title: "Comparar com exame anterior",
                                  text: "A série «\(match.description)» do exame anterior\(dateText(prior.date)) já está aberta.")
        }
        try database.openViewer(forSeries: match.uid)
        return MeasureOutcome(title: "Comparar com exame anterior",
                              text: "Aberta a série «\(match.description)» do exame anterior\(dateText(prior.date)).")
    }

    private static func dateText(_ date: Date?) -> String {
        guard let date else { return "" }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "pt_BR")
        formatter.dateFormat = "dd/MM/yyyy"
        return " de " + formatter.string(from: date)
    }
}
