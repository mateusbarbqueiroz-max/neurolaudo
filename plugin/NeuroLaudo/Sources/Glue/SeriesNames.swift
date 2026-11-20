//  NeuroLaudo — comando que lista os nomes de exame e de série do banco do IsiX.
//
//  Para o NeuroLaudo aprender os nomes do serviço sem ninguém digitar: o médico
//  copia a lista e a manda a quem mantém o programa. Lê só descrições de exame e
//  de série; nome do paciente, identificadores, datas e números não entram.

import Foundation
import IsiXPluginKit

@MainActor enum SeriesNames {
    /// Exames lidos por modalidade, os mais recentes.
    static let studiesPerModality = 300

    static func collect(database: IsiXDatabase, limit: Int = studiesPerModality) throws
        -> (entries: [CatalogEntry], studies: [CatalogStudy]) {
        var entries: [CatalogEntry] = []
        var studies: [CatalogStudy] = []
        for (code, _) in SeriesCatalog.modalities {
            for study in try database.studies(matching: IsiXStudyQuery(modality: code, limit: limit)) {
                let description = study.studyDescription ?? ""
                studies.append(CatalogStudy(modality: code, description: description))
                for series in try database.series(inStudy: study.studyInstanceUID) {
                    let modality = (series.modality ?? "").uppercased()
                    let name = series.seriesDescription ?? ""
                    // Só imagens da modalidade, e nada que o próprio NeuroLaudo gravou.
                    guard modality == code, !name.hasPrefix("NeuroLaudo") else { continue }
                    entries.append(CatalogEntry(modality: modality, studyDescription: description, seriesDescription: name))
                }
            }
        }
        return (entries, studies)
    }

    static func outcome(database: IsiXDatabase) throws -> MeasureOutcome {
        let found = try collect(database: database)
        let text = SeriesCatalog.report(found.entries, studies: found.studies, limitPerModality: studiesPerModality)
        let names = Set(found.entries.map { $0.modality + "|" + $0.seriesDescription.lowercased() }).count
        let read = { (code: String) in found.studies.filter { $0.modality == code }.count }
        PluginLog.note("nomes das séries: \(read("MR")) exame(s) de RM, \(read("CT")) de TC, \(names) nome(s) de série")
        return MeasureOutcome(title: "Nomes das séries", text: text)
    }
}
