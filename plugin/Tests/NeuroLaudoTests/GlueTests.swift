import XCTest
import IsiXPluginKit
@testable import NeuroLaudo

/// O complemento ativado em um IsiX de imitação, com os auxiliares dos testes.
@MainActor final class Harness {
    let context = IsiXPluginContext()
    let presenter = SilentPresenter()
    let plugin = NeuroLaudoPlugin()
    let settings = MemoryStore()

    /// `selfTest`: ativa como o teste automático no servidor Mac (-NeuroLaudoAutoteste YES).
    init(selfTest: Bool = false) throws {
        plugin.presenter = presenter
        plugin.settings = settings
        plugin.autoOpenDelay = 0
        if selfTest { settings.set(true, forKey: SelfTest.settingsKey) }
        try plugin.activate(with: context)
    }

    /// Um recebimento que terminou, com uma imagem por série informada.
    func arrival(_ seriesByStudy: [(study: String, series: String)], fromNetwork: Bool = true, complete: Bool = true) -> IsiXEvent {
        let images = seriesByStudy.enumerated().map { index, item in
            IsiXDatabaseImage(stubSOP: "sop-\(index)", series: item.series, study: item.study)
        }
        let network = fromNetwork ? ["PACS": images.map(\.sopInstanceUID)] : [:]
        return .imagesAdded(IsiXImagesAdded(stubImages: images, byCallingAETitle: network, isComplete: complete))
    }

    func geometry(spacing: Double = 1, interval: Double = 5) -> IsiXImageGeometry {
        IsiXImageGeometry(columns: 512, rows: 512, columnSpacing: spacing, rowSpacing: spacing,
                          imagePosition: IsiXVector3(x: -100, y: -100, z: 0),
                          rowDirection: IsiXVector3(x: 1, y: 0, z: 0), columnDirection: IsiXVector3(x: 0, y: 1, z: 0),
                          sliceThickness: 5, sliceInterval: interval, sliceLocation: 0)
    }

    @discardableResult
    func addViewer(modality: String = "CT", study: String = "study-1", series: String = "series-1",
                           description: String = "CRANIO", spacing: Double = 1, interval: Double = 5) -> IsiXViewer {
        let viewer = IsiXViewer(stubSeries: IsiXSeriesSummary(stubSliceCount: 40, currentSlice: 20, studyInstanceUID: study,
                                                              seriesInstanceUID: series, seriesDescription: description,
                                                              modality: modality),
                                geometry: geometry(spacing: spacing, interval: interval))
        context.stubViewers.append(viewer)
        return viewer
    }

    /// Linha em pixels; as coordenadas do paciente vêm da geometria, como no IsiX.
    @discardableResult
    func addLine(_ viewer: IsiXViewer, _ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double, slice: Int = 20,
                         selected: Bool = false, withPatientPoints: Bool = true) -> IsiXROI {
        let points = [IsiXPixelPoint(x: x0, y: y0), IsiXPixelPoint(x: x1, y: y1)]
        let roi = IsiXROI(stubKind: .line, name: "Length", slice: slice, points: points,
                          patientPoints: withPatientPoints ? points.map(viewer.stubGeometry.patientPoint(of:)) : [],
                          isSelected: selected)
        viewer.stubROIs.append(roi)
        return roi
    }

    func addPoint(_ viewer: IsiXViewer, _ x: Double, _ y: Double, slice: Int = 20) {
        let points = [IsiXPixelPoint(x: x, y: y)]
        viewer.stubROIs.append(IsiXROI(stubKind: .point, name: "Point", slice: slice, points: points,
                                       patientPoints: points.map(viewer.stubGeometry.patientPoint(of:))))
    }

    func loadStudies() {
        let day = 86_400.0
        context.stubDatabase.stubStudies = [
            IsiXStudy(stubUID: "study-1", patientID: "P1", studyDate: Date(timeIntervalSince1970: 100 * day), modalities: ["MR"]),
            IsiXStudy(stubUID: "study-0", patientID: "P1", studyDate: Date(timeIntervalSince1970: 40 * day), modalities: ["MR"]),
            IsiXStudy(stubUID: "other", patientID: "P2", studyDate: Date(timeIntervalSince1970: 90 * day), modalities: ["MR"]),
        ]
        context.stubDatabase.stubSeries = [
            IsiXSeries(stubUID: "s1-loc", studyUID: "study-1", description: "localizer", modality: "MR", imageCount: 3),
            IsiXSeries(stubUID: "s1-t1", studyUID: "study-1", description: "t1_mprage_sag_p2_iso", modality: "MR", imageCount: 176),
            IsiXSeries(stubUID: "s1-flair", studyUID: "study-1", description: "t2_tirm_tra_dark-fluid", modality: "MR", imageCount: 30),
            IsiXSeries(stubUID: "s1-dwi", studyUID: "study-1", description: "ep2d_diff_3scan_trace_p2", modality: "MR", imageCount: 60),
            IsiXSeries(stubUID: "s1-adc", studyUID: "study-1", description: "ep2d_diff_3scan_trace_p2_ADC", modality: "MR", imageCount: 30),
            IsiXSeries(stubUID: "s0-flair", studyUID: "study-0", description: "AX FLAIR", modality: "MR", imageCount: 28),
            IsiXSeries(stubUID: "s0-t1", studyUID: "study-0", description: "SAG T1", modality: "MR", imageCount: 25),
            IsiXSeries(stubUID: "o-flair", studyUID: "other", description: "t2_tirm_tra_dark-fluid", modality: "MR", imageCount: 30),
        ]
    }
}

/// Os comandos do complemento, executados como o menu do IsiX os executaria,
/// contra a imitação do IsiXPluginKit (LinuxCheck/IsiXPluginKitStub).
final class GlueTests: XCTestCase {
    /// O XCTest chama os testes na thread principal; o kit exige o ator principal.
    private func onMain(_ body: @MainActor (Harness) throws -> Void) throws {
        try MainActor.assumeIsolated { try body(Harness()) }
    }

    // MARK: registro

    func testActivationRegistersEveryCommandOnce() throws {
        try onMain { h in
        let ids = h.context.stubCommands.map(\.command.id)
        XCTAssertEqual(ids.count, 15)
        XCTAssertEqual(Set(ids).count, ids.count)
        for preset in NeuroWindowPresets.ct { XCTAssertTrue(ids.contains(preset.id)) }
        XCTAssertTrue(ids.contains(NeuroLaudoPlugin.Command.evans))
        XCTAssertTrue(ids.contains(NeuroLaudoPlugin.Command.comparePrior))
        // Comandos de imagem ficam desativados sem visualizador.
        let evans = try XCTUnwrap(h.context.stubCommands.first { $0.command.id == NeuroLaudoPlugin.Command.evans })
        XCTAssertEqual(evans.command.requirement, .viewer)
        }
    }

    // MARK: janelas

    func testWindowPresetCommand() throws {
        try onMain { h in
        let viewer = h.addViewer()
        try h.context.stubRun("janela-osso")
        XCTAssertEqual(viewer.stubWindowLevel, IsiXWindowLevel(center: 600, width: 2800))
        try h.context.stubRun("janela-encefalo")
        XCTAssertEqual(viewer.stubWindowLevel, IsiXWindowLevel(center: 40, width: 80))
        }
    }

    func testWindowPresetRefusesMR() throws {
        try onMain { h in
        let viewer = h.addViewer(modality: "MR")
        let before = viewer.stubWindowLevel
        XCTAssertThrowsError(try h.context.stubRun("janela-osso")) { error in
            XCTAssertTrue(NeuroLaudoPlugin.describe(error).contains("tomografia"))
        }
        XCTAssertEqual(viewer.stubWindowLevel, before)
        }
    }

    func testControlOptionDigitAppliesPreset() throws {
        try onMain { h in
        let viewer = h.addViewer()
        let handler = try XCTUnwrap(h.context.stubInputHandlers.first).handler
        func key(_ code: UInt16, _ flags: NSEvent.ModifierFlags) -> IsiXViewerInput {
            IsiXViewerInput(kind: .keyDown, viewerID: viewer.id, position: IsiXSlicePosition(slice: 20, phase: 0),
                            location: IsiXPixelPoint(x: 0, y: 0), modifierFlags: flags, keyCode: code)
        }
        XCTAssertTrue(handler(key(21, [.control, .option])))            // tecla 4 = Osso
        XCTAssertEqual(viewer.stubWindowLevel, IsiXWindowLevel(center: 600, width: 2800))
        XCTAssertFalse(handler(key(21, [])))                            // 4 sozinho segue para o IsiX
        XCTAssertFalse(handler(key(21, [.control, .option, .command])))
        XCTAssertFalse(handler(key(0, [.control, .option])))            // tecla que não é número
        XCTAssertEqual(viewer.stubWindowLevel, IsiXWindowLevel(center: 600, width: 2800))
        }
    }

    // MARK: Evans

    func testEvansCommand() throws {
        try onMain { h in
        let viewer = h.addViewer()
        let skull = h.addLine(viewer, 40, 200, 160, 200)   // 120 mm
        let horns = h.addLine(viewer, 80, 180, 122, 180)   // 42 mm
        h.addLine(viewer, 0, 0, 300, 0, slice: 5)          // outro corte: ignorada
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)
        let outcome = try XCTUnwrap(h.presenter.shown.last)
        XCTAssertEqual(outcome.title, "Índice de Evans")
        XCTAssertTrue(outcome.text.contains("0,35"), outcome.text)
        XCTAssertTrue(outcome.text.contains("ventriculomegalia"), outcome.text)
        XCTAssertEqual(viewer.stubROIs.first { $0.id == horns.id }?.name, "Cornos frontais")
        XCTAssertEqual(viewer.stubROIs.first { $0.id == skull.id }?.name, "Crânio (interno)")
        }
    }

    func testEvansNeedsExactlyTwoLinesOrTwoSelected() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 40, 200, 160, 200)
        XCTAssertThrowsError(try h.context.stubRun(NeuroLaudoPlugin.Command.evans)) { error in
            XCTAssertEqual(error as? MeasureError, .needsTwoLines(found: 1))
        }
        h.addLine(viewer, 80, 180, 116, 180)
        h.addLine(viewer, 0, 0, 10, 0)
        XCTAssertThrowsError(try h.context.stubRun(NeuroLaudoPlugin.Command.evans))
        XCTAssertTrue(h.presenter.shown.isEmpty)
        // Com duas selecionadas entre três, valem as selecionadas.
        viewer.stubROIs[0].isSelected = true
        viewer.stubROIs[1].isSelected = true
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)
        XCTAssertTrue(try XCTUnwrap(h.presenter.shown.last).text.contains("0,30"))
        }
    }

    func testLengthsUsePixelSpacingWhenPatientPointsAreMissing() throws {
        try onMain { h in
        let viewer = h.addViewer(spacing: 0.5)
        h.addLine(viewer, 0, 100, 240, 100, withPatientPoints: false)   // 240 px × 0,5 = 120 mm
        h.addLine(viewer, 0, 80, 84, 80, withPatientPoints: false)      // 84 px × 0,5 = 42 mm
        try h.context.stubRun(NeuroLaudoPlugin.Command.evans)
        let text = try XCTUnwrap(h.presenter.shown.last).text
        XCTAssertTrue(text.contains("42,0 mm") && text.contains("120,0 mm"), text)
        }
    }

    // MARK: linha média

    func testMidlineShiftWithLineAndPoint() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 100, 20, 100, 190)      // linha média em x = 100 px → x = 0 mm
        h.addPoint(viewer, 106.2, 100)            // septo 6,2 mm para +x (esquerda do paciente)
        try h.context.stubRun(NeuroLaudoPlugin.Command.midline)
        XCTAssertEqual(try XCTUnwrap(h.presenter.shown.last).text, "Desvio das estruturas da linha média de 6,2 mm para a esquerda.")
        XCTAssertTrue(viewer.stubROIs.contains { $0.name == "Linha média" })
        XCTAssertTrue(viewer.stubROIs.contains { $0.name == "Septo pelúcido" })
        }
    }

    func testMidlineShiftWithTwoLines() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 100, 20, 100, 190)
        h.addLine(viewer, 100, 100, 95, 100)      // da linha média até o septo, 5 mm para −x (direita)
        try h.context.stubRun(NeuroLaudoPlugin.Command.midline)
        XCTAssertEqual(try XCTUnwrap(h.presenter.shown.last).text, "Desvio das estruturas da linha média de 5,0 mm para a direita.")
        }
    }

    func testMidlineShiftNeedsBoth() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 100, 20, 100, 190)
        XCTAssertThrowsError(try h.context.stubRun(NeuroLaudoPlugin.Command.midline)) { error in
            XCTAssertEqual(error as? MeasureError, .needsLineAndPoint)
        }
        }
    }

    // MARK: ABC/2

    func testHematomaCommand() throws {
        try onMain { h in
        let viewer = h.addViewer(interval: 5)
        h.addLine(viewer, 100, 100, 140, 100)     // A = 40 mm
        h.addLine(viewer, 120, 85, 120, 115)      // B = 30 mm
        h.presenter.sliceCountAnswer = 4          // C = 4 × 5 = 20 mm
        try h.context.stubRun(NeuroLaudoPlugin.Command.hematoma)
        let outcome = try XCTUnwrap(h.presenter.shown.last)
        XCTAssertEqual(outcome.text, "Hematoma medindo 4,0 x 3,0 x 2,0 cm, com volume estimado de 12,0 mL (método ABC/2).")
        XCTAssertTrue(viewer.stubROIs.contains { $0.name == "Hematoma A" })
        }
    }

    func testHematomaCancelledShowsNothing() throws {
        try onMain { h in
        let viewer = h.addViewer()
        h.addLine(viewer, 100, 100, 140, 100)
        h.addLine(viewer, 120, 85, 120, 115)
        h.presenter.sliceCountAnswer = nil
        try h.context.stubRun(NeuroLaudoPlugin.Command.hematoma)
        XCTAssertTrue(h.presenter.shown.isEmpty)
        }
    }

    func testHematomaFallsBackToSliceThickness() throws {
        try onMain { h in
        let viewer = h.addViewer(interval: 0)     // sem intervalo: usa a espessura (5 mm)
        h.addLine(viewer, 100, 100, 140, 100)
        h.addLine(viewer, 120, 85, 120, 115)
        h.presenter.sliceCountAnswer = 2
        try h.context.stubRun(NeuroLaudoPlugin.Command.hematoma)
        XCTAssertTrue(try XCTUnwrap(h.presenter.shown.last).text.contains("6,0 mL"))
        }
    }

    // MARK: ASPECTS

    func testAspectsOpensPanel() throws {
        try onMain { h in
        try h.context.stubRun(NeuroLaudoPlugin.Command.aspects)
        XCTAssertEqual(h.presenter.aspectsRequests, 1)
        }
    }

    // MARK: protocolo e comparação


    func testProtocolOpensSeriesInOrderAndReportsMissing() throws {
        try onMain { h in
        h.loadStudies()
        h.context.stubDatabase.stubSelection = IsiXDatabaseSelection(stubStudies: [h.context.stubDatabase.stubStudies[0]])
        try h.context.stubRun(NeuroLaudoPlugin.Command.protocolAuto)
        XCTAssertEqual(h.context.stubDatabase.stubOpened, ["s1-flair", "s1-dwi", "s1-adc", "s1-t1"])
        let outcome = try XCTUnwrap(h.presenter.shown.last)
        XCTAssertTrue(outcome.text.contains("Não encontrei: SWI ou T2*, T1 pós-contraste."), outcome.text)
        }
    }

    func testProtocolSkipsSeriesAlreadyOpen() throws {
        try onMain { h in
        h.loadStudies()
        h.addViewer(modality: "MR", study: "study-1", series: "s1-flair", description: "t2_tirm_tra_dark-fluid")
        try h.context.stubRun(NeuroLaudoPlugin.Command.protocolAuto)
        XCTAssertEqual(h.context.stubDatabase.stubOpened, ["s1-dwi", "s1-adc", "s1-t1"])
        }
    }

    func testProtocolWithoutStudyExplainsWhatToDo() throws {
        try onMain { h in
        XCTAssertThrowsError(try h.context.stubRun(NeuroLaudoPlugin.Command.protocolAuto)) { error in
            XCTAssertTrue(NeuroLaudoPlugin.describe(error).contains("Selecione um exame"))
        }
        }
    }

    func testCompareWithPriorOpensCounterpart() throws {
        try onMain { h in
        h.loadStudies()
        h.addViewer(modality: "MR", study: "study-1", series: "s1-flair", description: "t2_tirm_tra_dark-fluid")
        try h.context.stubRun(NeuroLaudoPlugin.Command.comparePrior)
        // Abre a FLAIR do exame anterior do mesmo paciente, não a de outro paciente.
        XCTAssertEqual(h.context.stubDatabase.stubOpened, ["s0-flair"])
        }
    }

    func testCompareWithPriorWithoutPriorExplains() throws {
        try onMain { h in
        h.loadStudies()
        h.addViewer(modality: "MR", study: "study-0", series: "s0-flair", description: "AX FLAIR")
        XCTAssertThrowsError(try h.context.stubRun(NeuroLaudoPlugin.Command.comparePrior)) { error in
            XCTAssertTrue(NeuroLaudoPlugin.describe(error).contains("Não há exame anterior"))
        }
        XCTAssertTrue(h.context.stubDatabase.stubOpened.isEmpty)
        }
    }

    // MARK: fim

    func testDeactivateReleasesEverything() throws {
        try onMain { h in
        h.plugin.deactivate()
        XCTAssertNil(h.plugin.presenter)
        }
    }
}
