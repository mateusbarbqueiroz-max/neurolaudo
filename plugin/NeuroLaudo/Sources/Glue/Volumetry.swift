//  NeuroLaudo — volumetria cerebral da série aberta. Uso em pesquisa, não validado para diagnóstico.
//
//  O complemento não mede nada: entrega a série ao motor (programa em Python
//  instalado à parte, ver mac/instalar-volumetria.sh) e grava no exame o que o
//  motor devolve. Passos:
//    1. no visualizador: copia os cortes da série T1 para um arquivo NIfTI;
//    2. em segundo plano: roda o motor e acompanha o andamento;
//    3. de volta à janela: grava o relatório e o mapa colorido como séries do
//       exame e mostra o resumo.
//  A pasta temporária, com a imagem e o nome do paciente, é apagada no fim.

import Foundation
import IsiXPluginKit

extension SliceGeometry {
    init(_ g: IsiXImageGeometry) {
        self.init(columns: g.columns, rows: g.rows, columnSpacing: g.columnSpacing, rowSpacing: g.rowSpacing,
                  position: Vec3(g.imagePosition), rowDirection: Vec3(g.rowDirection),
                  columnDirection: Vec3(g.columnDirection))
    }
}

/// Um pedido de volumetria já fora do visualizador: só cópias, pode ir para segundo plano.
struct VolumetryJob: Sendable {
    /// Pasta temporária do pedido; tudo o mais fica dentro dela.
    var folder: URL
    var nifti: URL
    var header: URL
    var output: URL
    var progressFile: URL
    var studyInstanceUID: String
    var sourceSOPInstanceUID: String?
    /// Geometria dos cortes, na ordem em que foram gravados no volume.
    var geometries: [IsiXImageGeometry]
    /// Para cada corte do volume, o número que ele tem na série original.
    var order: [Int]
    var columns: Int
    var rows: Int
    /// Sentido dos índices do volume, por exemplo "PIR". O motor tem de ler o mesmo do arquivo.
    var orientation: String
}

/// O que o motor devolve em resultado.json.
struct VolumetryResult: Sendable, Equatable {
    struct Page: Sendable, Equatable {
        var file: String
        var width: Int
        var height: Int
    }

    var summary: [String]
    var reportSentence: String
    var warnings: [String]
    var disclaimer: String
    var pages: [Page]
    var mapFile: String
    var mapColumns: Int
    var mapRows: Int
    var mapSlices: Int
    var orientation: String

    static func load(from folder: URL) throws -> VolumetryResult {
        let data = try Data(contentsOf: folder.appendingPathComponent("resultado.json"))
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let map = root["mapa"] as? [String: Any], let mapFile = map["arquivo"] as? String,
              let columns = map["colunas"] as? Int, let rows = map["linhas"] as? Int, let slices = map["cortes"] as? Int,
              let pagesRaw = root["paginas"] as? [[String: Any]] else {
            throw PluginFailure("O motor de volumetria devolveu um resultado que não consegui ler.")
        }
        let pages = pagesRaw.compactMap { page -> Page? in
            guard let file = page["arquivo"] as? String, let width = page["largura"] as? Int,
                  let height = page["altura"] as? Int else { return nil }
            return Page(file: file, width: width, height: height)
        }
        let input = root["entrada"] as? [String: Any]
        return VolumetryResult(summary: root["resumo"] as? [String] ?? [],
                               reportSentence: root["frase_laudo"] as? String ?? "",
                               warnings: root["avisos"] as? [String] ?? [],
                               disclaimer: root["aviso"] as? String ?? Volumetry.disclaimer,
                               pages: pages, mapFile: mapFile, mapColumns: columns, mapRows: rows, mapSlices: slices,
                               orientation: input?["orientacao"] as? String ?? "")
    }
}

/// Quem roda o motor. Nos testes, um de mentira.
protocol VolumetryEngine: Sendable {
    /// Falha com uma frase para o usuário se o motor não estiver instalado.
    func checkInstalled() throws
    /// Roda o motor até o fim (bloqueia), informando o andamento. Deixa os resultados em `job.output`.
    func run(_ job: VolumetryJob, progress: IsiXTaskProgress) throws
}

/// O motor de verdade: o Python instalado por mac/instalar-volumetria.sh.
struct ProcessEngine: VolumetryEngine {
    /// Preferência do IsiX que troca a pasta do motor (usada no teste automático).
    static let homeKey = "NeuroLaudoMotor"
    static let notInstalled = "O motor de volumetria não está instalado neste Mac. "
        + "Siga o passo \"Volumetria\" do guia de instalação do NeuroLaudo e chame o comando de novo."

    var home: URL

    static func standard() -> ProcessEngine {
        if let custom = UserDefaults.standard.string(forKey: homeKey), !custom.isEmpty {
            return ProcessEngine(home: URL(fileURLWithPath: custom))
        }
        let support = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/NeuroLaudo/motor")
        return ProcessEngine(home: support)
    }

    var python: URL { home.appendingPathComponent("venv/bin/python") }

    func checkInstalled() throws {
        guard FileManager.default.isExecutableFile(atPath: python.path) else { throw PluginFailure(Self.notInstalled) }
    }

    func run(_ job: VolumetryJob, progress: IsiXTaskProgress) throws {
        try checkInstalled()
        let log = job.folder.appendingPathComponent("motor.txt")
        FileManager.default.createFile(atPath: log.path, contents: nil)
        let logHandle = try FileHandle(forWritingTo: log)
        defer { try? logHandle.close() }

        let process = Process()
        process.executableURL = python
        process.arguments = ["-m", "neurolaudo.volumetry.cli", "exame", "--nifti", job.nifti.path,
                             "--saida", job.output.path, "--cabecalho", job.header.path,
                             "--progresso", job.progressFile.path]
        var environment = ProcessInfo.processInfo.environment
        environment["NEUROLAUDO_MOTOR"] = home.path
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment
        process.standardOutput = logHandle
        process.standardError = logHandle
        try process.run()
        // O motor grava o andamento em um arquivo; ler o arquivo dispensa canais entre os processos.
        while process.isRunning {
            if progress.isCancelled { process.terminate() }
            if let step = Self.readProgress(job.progressFile) { progress.report(step.fraction, message: step.message) }
            Thread.sleep(forTimeInterval: 0.25)
        }
        process.waitUntilExit()
        if progress.isCancelled { throw CancellationError() }
        guard process.terminationStatus == 0 else {
            let text = (try? String(contentsOf: log, encoding: .utf8)) ?? ""
            throw PluginFailure(Self.failureMessage(fromLog: text, status: process.terminationStatus))
        }
    }

    static func readProgress(_ file: URL) -> (fraction: Double, message: String)? {
        guard let text = try? String(contentsOf: file, encoding: .utf8) else { return nil }
        let parts = text.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "\t", maxSplits: 1)
        guard parts.count == 2, let fraction = Double(parts[0]) else { return nil }
        return (fraction, String(parts[1]))
    }

    /// A frase de erro do motor ("Erro: ...") ou, se não houver, o fim do que ele escreveu.
    static func failureMessage(fromLog text: String, status: Int32) -> String {
        let lines = text.split(separator: "\n").map(String.init)
        if let index = lines.lastIndex(where: { $0.hasPrefix("Erro: ") }) {
            let message = lines[index...].joined(separator: "\n").dropFirst("Erro: ".count)
            return "A volumetria não terminou. " + String(message.prefix(900))
        }
        let tail = lines.suffix(6).joined(separator: "\n")
        return "A volumetria não terminou (código \(status))." + (tail.isEmpty ? "" : "\n" + String(tail.prefix(900)))
    }
}

/// O que ficou gravado no exame.
struct VolumetryStored: Sendable, Equatable {
    var reportSeriesUID: String?
    var mapSeriesUID: String?
}

enum Volumetry {
    static let title = "Volumetria cerebral (pesquisa)"
    static let disclaimer = "Uso em pesquisa. Não validado para diagnóstico."
    static let reportSeriesName = "NeuroLaudo: volumetria (pesquisa)"
    static let mapSeriesName = "NeuroLaudo: mapa da segmentação (pesquisa)"
    static let minimumSlices = 60

    // MARK: 1. no visualizador

    /// Avisos sobre a série, a julgar pelo nome. Lança se a série claramente não serve.
    static func seriesNotes(description: String) throws -> [String] {
        let kind = SeriesClassifier.classify(description: description, modality: "MR")
        switch kind {
        case .t1:
            return []
        case .t1Contrast:
            return ["A série parece ser T1 com contraste (\"\(description)\"). A referência é de T1 sem contraste."]
        case .other:
            return ["Não reconheci a série \"\(description)\" como T1. A referência é de T1 volumétrico sem contraste."]
        default:
            throw PluginFailure("A série aberta parece ser \(kind.label), não um T1 volumétrico. "
                + "Abra a série T1 3D sem contraste e chame o comando de novo.")
        }
    }

    /// Idade em anos na data do exame, com uma casa decimal.
    static func age(birth: Date?, exam: Date?) -> Double? {
        guard let birth, let exam, exam > birth else { return nil }
        let years = exam.timeIntervalSince(birth) / (365.2425 * 86_400)
        return (years * 10).rounded() / 10
    }

    static func dicomDate(_ date: Date?) -> String? {
        guard let date else { return nil }
        let parts = Calendar(identifier: .gregorian).dateComponents([.year, .month, .day], from: date)
        guard let year = parts.year, let month = parts.month, let day = parts.day else { return nil }
        return String(format: "%04d%02d%02d", year, month, day)
    }

    /// Copia a série aberta para um arquivo NIfTI e prepara o pedido ao motor.
    @MainActor static func prepare(viewer: IsiXViewer, context: IsiXPluginContext,
                                   temporary: URL = FileManager.default.temporaryDirectory) throws -> VolumetryJob {
        let summary = try viewer.series()
        guard (summary.modality ?? "").uppercased() == "MR" else {
            throw PluginFailure("A volumetria precisa de uma série de ressonância (T1 volumétrico). Esta série é de "
                + "\(summary.modality ?? "modalidade desconhecida").")
        }
        guard summary.phaseCount <= 1 else {
            throw PluginFailure("Esta série tem mais de um volume (\(summary.phaseCount) fases). Abra a série T1 volumétrica.")
        }
        guard summary.sliceCount >= minimumSlices else {
            throw PluginFailure("Esta série tem \(summary.sliceCount) cortes. A volumetria precisa do T1 volumétrico "
                + "(3D), com pelo menos \(minimumSlices) cortes.")
        }
        guard let studyUID = summary.studyInstanceUID else {
            throw PluginFailure("Não consegui identificar o exame desta série.")
        }
        let description = summary.seriesDescription ?? ""
        let notes = try seriesNotes(description: description)

        let geometries = try (0..<summary.sliceCount).map { try viewer.geometry(slice: $0) }
        let grid: VolumeGrid
        do {
            grid = try VolumeGrid.make(geometries.map(SliceGeometry.init))
        } catch let error as VolumeGridError {
            throw PluginFailure(error.errorDescription ?? "A série não forma um volume regular.")
        }

        let folder = temporary.appendingPathComponent("NeuroLaudo-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true,
                                                attributes: [.posixPermissions: 0o700])
        var job = VolumetryJob(folder: folder, nifti: folder.appendingPathComponent("t1.nii"),
                               header: folder.appendingPathComponent("cabecalho.json"),
                               output: folder.appendingPathComponent("saida"),
                               progressFile: folder.appendingPathComponent("andamento.txt"),
                               studyInstanceUID: studyUID, sourceSOPInstanceUID: nil,
                               geometries: grid.order.map { geometries[$0] }, order: grid.order,
                               columns: grid.columns, rows: grid.rows,
                               orientation: grid.orientationCode)
        do {
            FileManager.default.createFile(atPath: job.nifti.path, contents: nil)
            let handle = try FileHandle(forWritingTo: job.nifti)
            defer { try? handle.close() }
            try handle.write(contentsOf: Data(Nifti.header(for: grid)))
            for index in grid.order {
                let image = try viewer.image(slice: index)
                guard let pixels = image.scalarPixels, pixels.width == grid.columns, pixels.height == grid.rows else {
                    throw PluginFailure("A série aberta é colorida ou tem cortes de tamanhos diferentes: não é um T1 volumétrico.")
                }
                if job.sourceSOPInstanceUID == nil { job.sourceSOPInstanceUID = image.attributes.sopInstanceUID }
                try handle.write(contentsOf: Nifti.bytes(of: pixels.samples))
            }

            let study = try context.database().study(withInstanceUID: studyUID)
            var header: [String: Any] = ["serie": description, "avisos": notes]
            if let name = study?.patientName { header["nome"] = name }
            if let id = study?.patientID { header["id"] = id }
            if let sex = study?.patientSex { header["sexo"] = sex }
            if let age = age(birth: study?.patientBirthDate, exam: study?.studyDate) { header["idade"] = age }
            if let date = dicomDate(study?.studyDate) { header["data"] = date }
            try JSONSerialization.data(withJSONObject: header).write(to: job.header)
        } catch {
            try? FileManager.default.removeItem(at: folder)
            throw error
        }
        return job
    }

    // MARK: 2. em segundo plano

    /// Lê as páginas e o mapa que o motor gravou e monta os pedidos de gravação no exame.
    static func requests(for job: VolumetryJob, result: VolumetryResult) throws
        -> (report: IsiXDerivedSeriesRequest, map: IsiXDerivedSeriesRequest) {
        // O motor leu do arquivo a mesma orientação que o complemento calculou? Se não, nada é gravado.
        guard result.orientation == job.orientation else {
            throw PluginFailure("O motor leu o volume com orientação \(result.orientation), e o complemento gravou "
                + "\(job.orientation). Nada foi gravado no exame; avise quem mantém o NeuroLaudo.")
        }
        guard result.mapColumns == job.columns, result.mapRows == job.rows, result.mapSlices == job.geometries.count else {
            throw PluginFailure("O mapa devolvido pelo motor não tem o tamanho da série. Nada foi gravado no exame.")
        }
        var pages: [IsiXPixelData] = []
        for page in result.pages {
            let data = try Data(contentsOf: job.output.appendingPathComponent(page.file))
            pages.append(.rgba8(try IsiXPixelBuffer(width: page.width, height: page.height, channels: 4, samples: [UInt8](data))))
        }
        guard !pages.isEmpty else { throw PluginFailure("O motor não devolveu as páginas do relatório.") }
        var report = IsiXDerivedSeriesRequest(studyInstanceUID: job.studyInstanceUID, seriesDescription: reportSeriesName,
                                              images: pages)
        report.sourceSOPInstanceUID = job.sourceSOPInstanceUID

        let mapData = try Data(contentsOf: job.output.appendingPathComponent(result.mapFile))
        let sliceBytes = job.columns * job.rows * 4
        guard mapData.count == sliceBytes * job.geometries.count else {
            throw PluginFailure("O mapa devolvido pelo motor está incompleto. Nada foi gravado no exame.")
        }
        // O mapa vai para o exame na ordem da série original, para o corte n do mapa ser o corte n do T1.
        var slices = [IsiXPixelData?](repeating: nil, count: job.geometries.count)
        var geometries = job.geometries
        for k in 0..<job.geometries.count {
            let start = mapData.startIndex + k * sliceBytes
            let samples = [UInt8](mapData[start..<start + sliceBytes])
            let original = job.order.indices.contains(k) ? job.order[k] : k
            guard slices.indices.contains(original) else {
                throw PluginFailure("A ordem dos cortes da série não fecha com o mapa. Nada foi gravado no exame.")
            }
            slices[original] = .rgba8(try IsiXPixelBuffer(width: job.columns, height: job.rows, channels: 4, samples: samples))
            geometries[original] = job.geometries[k]
        }
        var map = IsiXDerivedSeriesRequest(studyInstanceUID: job.studyInstanceUID, seriesDescription: mapSeriesName,
                                           images: slices.compactMap { $0 })
        map.sourceSOPInstanceUID = job.sourceSOPInstanceUID
        map.geometries = geometries
        return (report, map)
    }

    // MARK: 3. de volta à janela

    /// Grava as duas séries no exame. Os arquivos intermediários do IsiX são apagados depois de importados.
    @MainActor static func store(report: IsiXDerivedSeriesRequest, map: IsiXDerivedSeriesRequest,
                                 context: IsiXPluginContext) throws -> VolumetryStored {
        let database = try context.database()
        var stored = VolumetryStored()
        for (request, isReport) in [(report, true), (map, false)] {
            let files = try database.writeDerivedSeries(request)
            defer { files.forEach { try? FileManager.default.removeItem(at: $0) } }
            let imported = try database.importFiles(at: files)
            guard imported.failures.isEmpty, let uid = imported.seriesInstanceUIDs.first else {
                let reason = imported.failures.first?.reason ?? "nenhuma série criada"
                let partial = stored.reportSeriesUID != nil ? " O relatório já foi gravado no exame; só o mapa faltou." : ""
                throw PluginFailure("O IsiX não importou \(isReport ? "o relatório" : "o mapa colorido") (\(reason))." + partial)
            }
            if isReport { stored.reportSeriesUID = uid } else { stored.mapSeriesUID = uid }
        }
        return stored
    }

    static func outcome(_ result: VolumetryResult) -> MeasureOutcome {
        var text = result.reportSentence
        if !result.warnings.isEmpty {
            text += "\n\nAvisos:\n" + result.warnings.map { "• " + $0 }.joined(separator: "\n")
        }
        text += "\n\nO relatório e o mapa colorido da segmentação foram gravados no exame, como duas séries novas. "
            + "Confira no mapa se cada estrutura está no lugar e do lado certo antes de usar os números."
        return MeasureOutcome(title: "Volumetria cerebral. \(result.disclaimer)", text: text)
    }

    /// Passos 2 e 3, com a pasta temporária apagada no fim, dê certo ou não.
    static func perform(_ job: VolumetryJob, engine: any VolumetryEngine, context: IsiXPluginContext,
                        progress: IsiXTaskProgress) async -> (outcome: MeasureOutcome, stored: VolumetryStored?) {
        defer { try? FileManager.default.removeItem(at: job.folder) }
        do {
            try engine.run(job, progress: progress)
            let result = try VolumetryResult.load(from: job.output)
            let requests = try requests(for: job, result: result)
            progress.report(0.98, message: "Gravando no exame")
            let stored = try await MainActor.run {
                try store(report: requests.report, map: requests.map, context: context)
            }
            return (outcome(result), stored)
        } catch is CancellationError {
            return (MeasureOutcome(title: title, text: "Volumetria cancelada. Nada foi gravado no exame."), nil)
        } catch {
            return (MeasureOutcome(title: title, text: describe(error)), nil)
        }
    }

    static func describe(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription ?? String(describing: error)
    }
}
