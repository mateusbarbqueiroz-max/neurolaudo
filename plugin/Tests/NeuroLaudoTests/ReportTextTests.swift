import XCTest
import IsiXPluginKit
@testable import NeuroLaudo

/// O texto para o laudo: as frases guardadas por exame e o comando que as junta.
final class ReportTextTests: XCTestCase {
    private func onMain(_ body: @MainActor (Harness) throws -> Void) throws {
        try MainActor.assumeIsolated { try body(Harness()) }
    }

    private let midline = "Desvio das estruturas da linha média de 6,2 mm para a esquerda."
    private let hematoma = "Hematoma medindo 4,0 x 3,0 x 2,0 cm, com volume estimado de 12,0 mL (método ABC/2)."
    private let evans = "Índice de Evans: 0,35, acima de 0,30 (sugere ventriculomegalia). "
        + "Cornos frontais 42,0 mm; diâmetro interno do crânio 120,0 mm."

    // MARK: núcleo

    func testBookKeepsTheLastOfEachKindInReportOrder() {
        var book = ReportBook()
        XCTAssertTrue(book.isEmpty)
        book.record(ReportEntry(kind: .volumetry, sentence: "V"))
        book.record(ReportEntry(kind: .evans, sentence: "E1"))
        book.record(ReportEntry(kind: .midline, sentence: "L", warning: "aviso"))
        book.record(ReportEntry(kind: .evans, sentence: "E2"))
        XCTAssertEqual(book.text, "L\nE2\nV")
        XCTAssertEqual(book.warnings, ["aviso"])
        book.remove(.midline)
        XCTAssertEqual(book.text, "E2\nV")
        XCTAssertTrue(book.warnings.isEmpty)
    }

    func testStoreForgetsTheOldestStudiesAndEmptyBooks() {
        var store = ReportStore()
        for n in 0...ReportStore.capacity {
            store.record(ReportEntry(kind: .evans, sentence: "E\(n)"), study: "s\(n)")
        }
        XCTAssertNil(store.book(for: "s0"))
        XCTAssertEqual(store.book(for: "s1")?.text, "E1")
        XCTAssertEqual(store.recent.count, ReportStore.capacity)
        // Medir de novo um exame antigo o traz para o fim da fila.
        store.record(ReportEntry(kind: .midline, sentence: "L"), study: "s1")
        XCTAssertEqual(store.lastStudy, "s1")
        store.remove(.midline, study: "s1")
        store.remove(.evans, study: "s1")
        XCTAssertNil(store.book(for: "s1"))
        XCTAssertNotEqual(store.lastStudy, "s1")
    }

    func testHematomaWarningIsSeparateFromTheSentence() throws {
        let a = Segment(start: Vec3(x: 0, y: 0, z: 0), end: Vec3(x: 40, y: 0, z: 0))
        let b = Segment(start: Vec3(x: 0, y: 0, z: 0), end: Vec3(x: 21.2, y: 21.2, z: 0))
        let result = try NeuroMeasures.hematoma(a, b, sliceCount: 2, sliceIntervalMM: 5)
        XCTAssertFalse(result.sentence.contains("Atenção"))
        XCTAssertTrue(try XCTUnwrap(result.warning).contains("45°"))
        XCTAssertEqual(result.summary, result.sentence + " " + (result.warning ?? ""))
    }

    // MARK: comando

    /// Evans, linha média e ABC/2 no mesmo exame, uma medida de cada vez, como o usuário faria.
    @MainActor private func measureAll(_ h: Harness, _ viewer: IsiXViewer) throws {
        h.addLine(viewer, 40, 200, 160, 200)      // 120 mm
        h.addLine(viewer, 80, 180, 122, 180)      // 42 mm
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)
        viewer.stubROIs.removeAll()
        h.addLine(viewer, 100, 20, 100, 190)
        h.addPoint(viewer, 106.2, 100)
        try h.context.stubRun(NeuroLaudoPlugin.Command.midline)
        viewer.stubROIs.removeAll()
        h.addLine(viewer, 100, 100, 140, 100)
        h.addLine(viewer, 120, 85, 120, 115)
        h.presenter.sliceCountAnswer = 4
        try h.context.stubRun(NeuroLaudoPlugin.Command.hematoma)
    }

    func testReportTextJoinsTheStudyMeasuresInReportOrder() throws {
        try onMain { h in
        h.loadStudies()
        let viewer = h.addViewer()
        try measureAll(h, viewer)
        try h.context.stubRun(NeuroLaudoPlugin.Command.reportText)
        let outcome = try XCTUnwrap(h.presenter.shown.last)
        XCTAssertEqual(outcome.title, "Texto para o laudo")
        XCTAssertEqual(outcome.copyText, [midline, hematoma, evans].joined(separator: "\n"))
        XCTAssertTrue(outcome.text.hasPrefix(try XCTUnwrap(outcome.copyText)))
        XCTAssertTrue(outcome.text.contains("Exame: MR de "), outcome.text)
        XCTAssertFalse(outcome.text.contains("P1"))           // nada do paciente
        }
    }

    func testRemeasuringReplacesAndEachStudyHasItsOwnText() throws {
        try onMain { h in
        let first = h.addViewer(study: "study-1")
        h.addLine(first, 40, 200, 160, 200)
        h.addLine(first, 80, 180, 122, 180)
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)
        first.stubROIs.removeAll()
        h.addLine(first, 40, 200, 160, 200)
        h.addLine(first, 80, 180, 116, 180)       // 36 mm: 0,30
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)

        let second = h.addViewer(study: "study-2", series: "series-2")
        try h.context.stubRun(NeuroLaudoPlugin.Command.reportText, viewer: second)
        let empty = try XCTUnwrap(h.presenter.shown.last)
        XCTAssertEqual(empty.copyText, "")
        XCTAssertTrue(empty.text.hasPrefix("Ainda não há medidas deste exame"))

        try h.context.stubRun(NeuroLaudoPlugin.Command.reportText, viewer: first)
        let text = try XCTUnwrap(h.presenter.shown.last?.copyText)
        XCTAssertTrue(text.hasPrefix("Índice de Evans: 0,30"), text)
        XCTAssertFalse(text.contains("0,35"))
        XCTAssertFalse(text.contains("\n"))
        }
    }

    func testWithoutAnOpenSeriesTheLastMeasuredStudyIsShown() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 40, 200, 160, 200)
        h.addLine(viewer, 80, 180, 122, 180)
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)
        h.context.stubViewers.removeAll()
        try h.context.stubRun(NeuroLaudoPlugin.Command.reportText)
        XCTAssertEqual(h.presenter.shown.last?.copyText, evans)
        }
    }

    func testHematomaWarningStaysOutOfTheCopiedText() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 100, 100, 140, 100)
        h.addLine(viewer, 100, 100, 121.2, 121.2)  // 45°: o método pede perpendiculares
        h.presenter.sliceCountAnswer = 2
        try h.context.stubRun(NeuroLaudoPlugin.Command.hematoma)
        XCTAssertTrue(try XCTUnwrap(h.presenter.shown.last).text.contains("Atenção"))
        try h.context.stubRun(NeuroLaudoPlugin.Command.reportText)
        let outcome = try XCTUnwrap(h.presenter.shown.last)
        XCTAssertFalse(try XCTUnwrap(outcome.copyText).contains("Atenção"))
        XCTAssertTrue(outcome.text.contains("Antes de colar, confira:\n• Atenção"), outcome.text)
        }
    }

    func testAspectsChangesGoToTheTextOfTheStudyWhereThePanelWasOpened() throws {
        try onMain { h in
        h.addViewer(study: "study-1")
        try h.context.stubRun(NeuroLaudoPlugin.Command.aspects)
        XCTAssertEqual(h.presenter.aspectsStudy, "study-1")
        let sentence = try Aspects.summary(affected: ["I", "M2"], side: .left)
        h.presenter.aspectsChange?(sentence)
        try h.context.stubRun(NeuroLaudoPlugin.Command.reportText)
        XCTAssertEqual(h.presenter.shown.last?.copyText, sentence)
        // Limpar o painel tira o ASPECTS do texto.
        h.presenter.aspectsChange?(nil)
        try h.context.stubRun(NeuroLaudoPlugin.Command.reportText)
        XCTAssertEqual(h.presenter.shown.last?.copyText, "")
        }
    }

    func testDeactivateForgetsTheTexts() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 40, 200, 160, 200)
        h.addLine(viewer, 80, 180, 122, 180)
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)
        XCTAssertNotNil(h.plugin.reports.book(for: "study-1"))
        h.plugin.deactivate()
        XCTAssertNil(h.plugin.reports.book(for: "study-1"))
        }
    }
}
