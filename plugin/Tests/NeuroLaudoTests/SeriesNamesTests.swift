import XCTest
import IsiXPluginKit
@testable import NeuroLaudo

final class SeriesNamesTests: XCTestCase {
    func testCountsMergeSpellingsAndSortByFrequency() {
        let counted = SeriesCatalog.counts(["AX FLAIR", "ax  flair", "AX FLAIR", "SAG T1", " ", "ADC"])
        XCTAssertEqual(counted.map(\.name), ["AX FLAIR", "ADC", "SAG T1"])
        XCTAssertEqual(counted.map(\.count), [3, 1, 1])
    }

    func testReportShowsHowEachNameIsRecognized() {
        let entries = [
            CatalogEntry(modality: "MR", studyDescription: "RM ENCEFALO", seriesDescription: "t2_tirm_tra_dark-fluid"),
            CatalogEntry(modality: "MR", studyDescription: "RM ENCEFALO", seriesDescription: "t2_tirm_tra_dark-fluid"),
            CatalogEntry(modality: "MR", studyDescription: "RM CRANIO", seriesDescription: "Apparent Diffusion Coefficient (mm²/s)"),
            CatalogEntry(modality: "MR", studyDescription: "RM ENCEFALO", seriesDescription: "sequencia_xyz_123"),
        ]
        let text = SeriesCatalog.report(entries, studyCounts: ["MR": 3, "CT": 0], limitPerModality: 300)
        XCTAssertTrue(text.contains("Exames lidos: 3 de RM e 0 de TC (os mais recentes, até 300 de cada)."))
        XCTAssertTrue(text.contains("Nomes de exame: RM ENCEFALO (3) · RM CRANIO (1)"))
        XCTAssertTrue(text.contains("  t2_tirm_tra_dark-fluid (2) → FLAIR"))
        XCTAssertTrue(text.contains("  Apparent Diffusion Coefficient (mm²/s) (1) → ADC"))
        XCTAssertTrue(text.contains("  sequencia_xyz_123 (1) → não reconhecida"))
        XCTAssertTrue(text.contains("TC\n  nenhuma série de TC no banco"))
    }

    func testCommandListsOnlyNamesAndNeverPatientData() throws {
        try MainActor.assumeIsolated {
            let h = try Harness()
            var mr = IsiXStudy(stubUID: "1.2.3.4", patientID: "PRONT-98765", studyDescription: "RM ENCEFALO",
                               studyDate: Date(timeIntervalSince1970: 1_700_000_000), modalities: ["MR"])
            mr.patientName = "FULANO^DE TAL"
            mr.accessionNumber = "ACC-55555"
            var ct = IsiXStudy(stubUID: "1.2.3.5", patientID: "PRONT-98765", studyDescription: "TC CRANIO",
                               studyDate: Date(timeIntervalSince1970: 1_600_000_000), modalities: ["CT", "SR"])
            ct.patientName = "FULANO^DE TAL"
            h.context.stubDatabase.stubStudies = [mr, ct]
            h.context.stubDatabase.stubSeries = [
                IsiXSeries(stubUID: "9.1", studyUID: "1.2.3.4", description: "AX FLAIR", modality: "MR", imageCount: 28),
                IsiXSeries(stubUID: "9.2", studyUID: "1.2.3.4", description: "SAG T1 MPRAGE", modality: "MR", imageCount: 176),
                IsiXSeries(stubUID: "9.3", studyUID: "1.2.3.4", description: "NeuroLaudo: volumetria (pesquisa)", modality: "SC", imageCount: 2),
                IsiXSeries(stubUID: "9.4", studyUID: "1.2.3.5", description: "CRANIO 5mm", modality: "CT", imageCount: 30),
                IsiXSeries(stubUID: "9.5", studyUID: "1.2.3.5", description: "Dose Report", modality: "SR", imageCount: 1),
            ]
            try h.context.stubRun(NeuroLaudoPlugin.Command.seriesNames)
            let shown = try XCTUnwrap(h.presenter.shown.last)
            XCTAssertEqual(shown.title, "Nomes das séries")
            XCTAssertTrue(shown.text.contains("  AX FLAIR (1) → FLAIR"))
            XCTAssertTrue(shown.text.contains("  SAG T1 MPRAGE (1) → T1"))
            XCTAssertTrue(shown.text.contains("  CRANIO 5mm (1) → TC parênquima"))
            XCTAssertTrue(shown.text.contains("Nomes de exame: TC CRANIO (1)"))
            for secret in ["FULANO", "PRONT-98765", "ACC-55555", "1.2.3.4", "1.2.3.5", "9.1", "NeuroLaudo:", "Dose Report", "2023"] {
                XCTAssertFalse(shown.text.contains(secret), "não pode aparecer: \(secret)")
            }
        }
    }
}
