import XCTest
import IsiXPluginKit
@testable import NeuroLaudo

/// Motor de mentira: confere o que recebeu e grava um resultado do tamanho pedido.
final class FakeEngine: VolumetryEngine, @unchecked Sendable {
    var installed = true
    var failure: String?
    /// Orientação que o "motor" diz ter lido do arquivo; `nil` repete a do pedido.
    var orientation: String?
    /// Data do exame anterior que o "motor" diz ter comparado; `nil`: sem comparação.
    var comparedWith: String?
    private(set) var jobs: [VolumetryJob] = []

    func checkInstalled() throws {
        if !installed { throw PluginFailure(ProcessEngine.notInstalled) }
    }

    func run(_ job: VolumetryJob, progress: IsiXTaskProgress) throws {
        jobs.append(job)
        progress.report(0.5, message: "Segmentando")
        if let failure { throw PluginFailure(failure) }
        try FileManager.default.createDirectory(at: job.output, withIntermediateDirectories: true)
        let slices = job.geometries.count
        // Mapa: em cada pixel, o vermelho guarda o número do corte, para conferir a ordem.
        var map = [UInt8]()
        map.reserveCapacity(job.columns * job.rows * 4 * slices)
        for k in 0..<slices {
            for _ in 0..<(job.columns * job.rows) { map += [UInt8(k), 0, 0, 255] }
        }
        try Data(map).write(to: job.output.appendingPathComponent("mapa.rgba"))
        try Data([UInt8](repeating: 200, count: 3 * 2 * 4)).write(to: job.output.appendingPathComponent("pagina-1.rgba"))
        try Data([UInt8](repeating: 100, count: 3 * 2 * 4)).write(to: job.output.appendingPathComponent("pagina-2.rgba"))
        var result: [String: Any] = [
            "aviso": "Uso em pesquisa. Não validado para diagnóstico.",
            "resumo": ["Hipocampo esquerdo: 3,7 mL, percentil 2  ▼ abaixo do percentil 5"],
            "frase_laudo": "Volumetria cerebral automática: hipocampo esquerdo 3,7 mL (percentil 2).",
            "avisos": ["Aviso de teste."],
            "entrada": ["orientacao": orientation ?? job.orientation],
            "paginas": [["arquivo": "pagina-1.rgba", "largura": 3, "altura": 2], ["arquivo": "pagina-2.rgba", "largura": 3, "altura": 2]],
            "mapa": ["arquivo": "mapa.rgba", "colunas": job.columns, "linhas": job.rows, "cortes": slices],
        ]
        if let comparedWith { result["comparacao"] = ["anterior": ["data": comparedWith], "frase": "Comparação."] }
        try JSONSerialization.data(withJSONObject: result).write(to: job.output.appendingPathComponent("resultado.json"))
    }
}

extension Harness {
    /// Visualizador com um T1 sagital de 64 cortes de 6 × 5 pixels. O valor de cada pixel diz de que corte ele é.
    /// `reversed`: a série vem na ordem contrária (da direita para a esquerda do paciente).
    @discardableResult
    func addT1Viewer(description: String = "SAG T1 MPRAGE", modality: String = "MR", slices: Int = 64,
                     reversed: Bool = false, color: Bool = false) throws -> IsiXViewer {
        let viewer = IsiXViewer(stubSeries: IsiXSeriesSummary(stubSliceCount: slices, studyInstanceUID: "study-1",
                                                              seriesInstanceUID: "s1-t1", seriesDescription: description,
                                                              modality: modality),
                                geometry: geometry())
        for n in 0..<slices {
            let place = reversed ? slices - 1 - n : n
            // x em LPS: positivo é esquerda. O corte "place" 0 é o mais à esquerda.
            let geometry = IsiXImageGeometry(columns: 6, rows: 5, columnSpacing: 1, rowSpacing: 1,
                                             imagePosition: IsiXVector3(x: 40 - Double(place), y: -30, z: 20),
                                             rowDirection: IsiXVector3(x: 0, y: 1, z: 0),
                                             columnDirection: IsiXVector3(x: 0, y: 0, z: -1),
                                             sliceThickness: 1, sliceInterval: 1, sliceLocation: Double(place))
            let pixels: IsiXPixelData = color
                ? .rgba8(try IsiXPixelBuffer(width: 6, height: 5, channels: 4, samples: [UInt8](repeating: 0, count: 120)))
                : .float32(try IsiXPixelBuffer(width: 6, height: 5, samples: [Float](repeating: Float(place), count: 30)))
            viewer.stubSlices.append((geometry, pixels))
        }
        context.stubViewers.append(viewer)
        return viewer
    }

    func loadPatient() {
        var study = IsiXStudy(stubUID: "study-1", patientID: "P1", studyDate: Date(timeIntervalSince1970: 1_700_000_000),
                              modalities: ["MR"])
        study.patientName = "FANTOMA^TESTE"
        study.patientSex = "F"
        study.patientBirthDate = Date(timeIntervalSince1970: 1_700_000_000 - 70.5 * 365.2425 * 86_400)
        context.stubDatabase.stubStudies = [study]
    }
}

final class VolumetryTests: XCTestCase {
    private func onMain<T>(_ body: @MainActor () throws -> T) rethrows -> T {
        try MainActor.assumeIsolated(body)
    }

    private func scratch() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("nl-teste-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        addTeardownBlock { try? FileManager.default.removeItem(at: url) }
        return url
    }

    func testPrepareWritesTheSeriesAsAVolume() throws {
        let folder = try scratch()
        try onMain {
            let harness = try Harness()
            harness.loadPatient()
            let viewer = try harness.addT1Viewer(reversed: true)
            viewer.stubRepetitionTime = 2300
            viewer.stubEchoTime = 2.98
            let job = try Volumetry.prepare(viewer: viewer, context: harness.context, temporary: folder)

            XCTAssertEqual(job.orientation, "PIR")
            XCTAssertEqual([job.columns, job.rows, job.geometries.count], [6, 5, 64])
            XCTAssertEqual(job.studyInstanceUID, "study-1")
            XCTAssertNotNil(job.sourceSOPInstanceUID)
            // Os cortes vão para o volume da esquerda para a direita, qualquer que seja a ordem na série.
            XCTAssertEqual(job.geometries.first?.imagePosition.x, 40)
            XCTAssertEqual(job.geometries.last?.imagePosition.x, 40 - 63)

            let data = try Data(contentsOf: job.nifti)
            XCTAssertEqual(data.count, 352 + 6 * 5 * 64 * 4)
            func value(slice: Int) -> Float {
                let offset = 352 + slice * 6 * 5 * 4
                return Float(bitPattern: UInt32(littleEndian: data[offset..<offset + 4].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self) }))
            }
            XCTAssertEqual(value(slice: 0), 0)
            XCTAssertEqual(value(slice: 63), 63)

            let header = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: job.header)) as? [String: Any])
            XCTAssertEqual(header["nome"] as? String, "FANTOMA^TESTE")
            XCTAssertEqual(header["sexo"] as? String, "F")
            XCTAssertEqual(header["idade"] as? Double, 70.5)
            XCTAssertEqual(header["serie"] as? String, "SAG T1 MPRAGE")
            XCTAssertEqual((header["avisos"] as? [String])?.count, 0)
            XCTAssertEqual((header["data"] as? String)?.count, 8)
            // Para o histórico de comparação: o exame e os parâmetros da aquisição.
            XCTAssertEqual(header["id"] as? String, "P1")
            XCTAssertEqual(header["exame"] as? String, "study-1")
            XCTAssertEqual(header["aquisicao"] as? [String: Double], ["tr": 2300, "te": 2.98])
        }
    }

    func testSeriesThatDoNotFitAreRefused() throws {
        let folder = try scratch()
        try onMain {
            let harness = try Harness()
            harness.loadPatient()
            @MainActor func refusal(_ viewer: IsiXViewer) -> String {
                do {
                    _ = try Volumetry.prepare(viewer: viewer, context: harness.context, temporary: folder)
                    return ""
                } catch {
                    return Volumetry.describe(error)
                }
            }
            XCTAssertTrue(refusal(try harness.addT1Viewer(modality: "CT")).contains("ressonância"))
            XCTAssertTrue(refusal(try harness.addT1Viewer(slices: 24)).contains("24 cortes"))
            XCTAssertTrue(refusal(try harness.addT1Viewer(description: "AX FLAIR")).contains("FLAIR"))
            XCTAssertTrue(refusal(try harness.addT1Viewer(color: true)).contains("colorida"))
            let gap = try harness.addT1Viewer()
            gap.stubSlices.remove(at: 10)
            gap.stubSeries.sliceCount = 63
            XCTAssertTrue(refusal(gap).contains("igualmente espaçados"))
            // Nada fica para trás na pasta temporária quando o pedido é recusado.
            XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: folder.path), [])
        }
    }

    func testSeriesNameBecomesAWarningWhenItIsNotAPlainT1() throws {
        XCTAssertEqual(try Volumetry.seriesNotes(description: "t1_mprage_sag_p2_iso"), [])
        XCTAssertTrue(try XCTUnwrap(Volumetry.seriesNotes(description: "SAG T1 MPRAGE GD").first).contains("com contraste"))
        XCTAssertTrue(try XCTUnwrap(Volumetry.seriesNotes(description: "serie 7").first).contains("Não reconheci"))
        XCTAssertThrowsError(try Volumetry.seriesNotes(description: "AX DWI b1000"))
        XCTAssertEqual(Volumetry.age(birth: Date(timeIntervalSince1970: 0), exam: Date(timeIntervalSince1970: 365.2425 * 86_400 * 40.26)), 40.3)
        XCTAssertNil(Volumetry.age(birth: nil, exam: Date()))
        XCTAssertEqual(Volumetry.dicomDate(Date(timeIntervalSince1970: 1_700_000_000))?.prefix(4), "2023")
    }

    func testWholeCommandStoresReportAndMapInTheStudy() async throws {
        let engine = FakeEngine()
        engine.comparedWith = "20250310"
        let (harness, task) = try await MainActor.run { () -> (Harness, IsiXTask) in
            let harness = try Harness()
            harness.loadPatient()
            harness.plugin.engine = engine
            let viewer = try harness.addT1Viewer(reversed: true)     // série da direita para a esquerda
            return (harness, try harness.plugin.startVolumetry(in: viewer, context: harness.context))
        }
        try await task.value()
        try await MainActor.run {
            let database = harness.context.stubDatabase
            XCTAssertEqual(database.stubWritten.count, 2)
            let report = database.stubWritten[0].request
            let map = database.stubWritten[1].request
            XCTAssertEqual(report.seriesDescription, Volumetry.reportSeriesName)
            XCTAssertEqual(report.images.count, 2)
            XCTAssertNil(report.geometries)
            XCTAssertEqual(map.seriesDescription, Volumetry.mapSeriesName)
            XCTAssertEqual(map.images.count, 64)
            XCTAssertEqual(map.geometries?.count, 64)
            XCTAssertNotNil(map.sourceSOPInstanceUID)
            // O mapa segue a ordem da série original: o primeiro corte da série é o mais à direita (x = 40 - 63),
            // que no volume é o último (o motor de mentira pinta em cada corte o seu número no volume).
            guard case .rgba8(let first) = map.images[0], case .rgba8(let last) = map.images[63] else {
                return XCTFail("mapa sem cor")
            }
            XCTAssertEqual(first[0, 0, 0], 63)
            XCTAssertEqual(map.geometries?[0].imagePosition.x, 40 - 63)
            XCTAssertEqual(last[0, 0, 0], 0)
            XCTAssertEqual(map.geometries?[63].imagePosition.x, 40)

            // As duas séries entraram no exame, o mapa abriu e o resumo foi mostrado.
            let names = database.stubSeries.map { $0.seriesDescription ?? "" }
            XCTAssertTrue(names.contains(Volumetry.reportSeriesName) && names.contains(Volumetry.mapSeriesName))
            XCTAssertEqual(database.stubOpened.count, 1)
            let shown = try XCTUnwrap(harness.presenter.shown.last)
            XCTAssertTrue(shown.title.contains("Uso em pesquisa"))
            XCTAssertTrue(shown.text.contains("hipocampo esquerdo 3,7 mL") && shown.text.contains("Aviso de teste."))
            XCTAssertTrue(shown.text.contains("página de comparação com o exame de 10/03/2025"))
            // A pasta temporária, com a imagem e o nome do paciente, foi apagada, e os arquivos do IsiX também.
            let job = try XCTUnwrap(engine.jobs.first)
            XCTAssertFalse(FileManager.default.fileExists(atPath: job.folder.path))
            XCTAssertFalse(FileManager.default.fileExists(atPath: database.stubWritten[0].files[0].path))
        }
    }

    func testFailuresLeaveTheStudyUntouched() async throws {
        for scenario in ["motor", "orientacao"] {
            let engine = FakeEngine()
            if scenario == "motor" { engine.failure = "A segmentação falhou." } else { engine.orientation = "LIR" }
            let (harness, task) = try await MainActor.run { () -> (Harness, IsiXTask) in
                let harness = try Harness()
                harness.loadPatient()
                harness.plugin.engine = engine
                let viewer = try harness.addT1Viewer()
                return (harness, try harness.plugin.startVolumetry(in: viewer, context: harness.context))
            }
            try await task.value()
            try await MainActor.run {
                XCTAssertEqual(harness.context.stubDatabase.stubWritten.count, 0, scenario)
                let shown = try XCTUnwrap(harness.presenter.shown.last)
                XCTAssertTrue(shown.text.contains(scenario == "motor" ? "A segmentação falhou." : "orientação LIR"), shown.text)
                XCTAssertFalse(FileManager.default.fileExists(atPath: try XCTUnwrap(engine.jobs.first).folder.path))
            }
        }
    }

    func testMissingEngineIsExplainedBeforeAnythingIsCopied() throws {
        try onMain {
            let harness = try Harness()
            harness.loadPatient()
            let engine = FakeEngine()
            engine.installed = false
            harness.plugin.engine = engine
            let viewer = try harness.addT1Viewer()
            XCTAssertThrowsError(try harness.plugin.startVolumetry(in: viewer, context: harness.context)) {
                XCTAssertTrue(Volumetry.describe($0).contains("não está instalado"))
            }
            XCTAssertTrue(engine.jobs.isEmpty)
            XCTAssertTrue(harness.context.stubCommands.contains { $0.command.id == "volumetria" })
        }
    }

    /// O motor de verdade é um programa à parte; aqui um roteiro de shell faz o papel do Python.
    func testProcessEngineFollowsProgressAndReportsFailures() throws {
        let home = try scratch()
        let bin = home.appendingPathComponent("venv/bin")
        try FileManager.default.createDirectory(at: bin, withIntermediateDirectories: true)
        let engine = ProcessEngine(home: home)
        XCTAssertThrowsError(try engine.checkInstalled())

        func install(_ script: String) throws {
            let python = bin.appendingPathComponent("python")
            try script.write(to: python, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: python.path)
        }
        func job() throws -> VolumetryJob {
            let folder = home.appendingPathComponent(UUID().uuidString)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            return VolumetryJob(folder: folder, nifti: folder.appendingPathComponent("t1.nii"),
                                header: folder.appendingPathComponent("cabecalho.json"),
                                output: folder.appendingPathComponent("saida"),
                                progressFile: folder.appendingPathComponent("andamento.txt"),
                                studyInstanceUID: "study-1", sourceSOPInstanceUID: nil, geometries: [], order: [],
                                columns: 1, rows: 1,
                                orientation: "PIR")
        }
        // Os argumentos chegam como o motor espera: ... --saida S --cabecalho C --progresso P
        try install("""
            #!/bin/sh
            [ "$1" = "-m" ] && [ "$2" = "neurolaudo.volumetry.cli" ] && [ "$3" = "exame" ] || exit 9
            [ -n "$NEUROLAUDO_MOTOR" ] || exit 8
            [ "${12}" = "--historico" ] && [ -n "${13}" ] || exit 7
            printf '0.42\\tSegmentando\\n' > "${11}"
            sleep 1
            mkdir -p "$7" && echo ok > "$7/feito.txt"
            """)
        let first = try job()
        let progress = IsiXTaskProgress.stubMake()
        try engine.run(first, progress: progress)
        XCTAssertEqual(progress.fractionCompleted, 0.42)
        XCTAssertEqual(progress.message, "Segmentando")
        XCTAssertTrue(FileManager.default.fileExists(atPath: first.output.appendingPathComponent("feito.txt").path))

        try install("#!/bin/sh\necho 'Erro: a máscara do encéfalo veio vazia' >&2\nexit 1\n")
        XCTAssertThrowsError(try engine.run(try job(), progress: IsiXTaskProgress.stubMake())) {
            XCTAssertEqual(Volumetry.describe($0), "A volumetria não terminou. a máscara do encéfalo veio vazia")
        }
        XCTAssertEqual(ProcessEngine.failureMessage(fromLog: "", status: 3), "A volumetria não terminou (código 3).")
    }
}
