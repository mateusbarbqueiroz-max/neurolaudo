import XCTest
import IsiXPluginKit
@testable import NeuroLaudo

/// O autoteste que roda dentro do IsiX no servidor Mac, aqui contra a imitação
/// do kit: garante que ele mesmo está certo antes de servir de prova lá.
final class SelfTestTests: XCTestCase {
    func testEveryCheckPassesAndNothingIsLeftOnTheImage() throws {
        try MainActor.assumeIsolated {
            let h = try Harness(selfTest: true)
            let viewer = h.addViewer(spacing: 0.8, interval: 2.5)
            let checks = try SelfTest.run(in: viewer)
            XCTAssertEqual(checks.map(\.name), ["comprimento", "Evans", "linha média", "ABC/2", "janela"])
            for check in checks { XCTAssertTrue(check.passed, check.line) }
            XCTAssertTrue(viewer.stubROIs.isEmpty)
            // A janela que estava antes é devolvida.
            XCTAssertEqual(viewer.stubWindowLevel, IsiXWindowLevel(center: 40, width: 400))
        }
    }

    func testCommandExistsOnlyWhenAskedFor() throws {
        try MainActor.assumeIsolated {
            let normal = try Harness()
            XCTAssertFalse(normal.context.stubCommands.contains { $0.command.id == NeuroLaudoPlugin.Command.selfTest })
            let ci = try Harness(selfTest: true)
            XCTAssertEqual(ci.context.stubCommands.count, 15)
            ci.addViewer()
            try ci.context.stubRun(NeuroLaudoPlugin.Command.selfTest)
        }
    }

    func testReportsFailureInsteadOfPassingSilently() throws {
        try MainActor.assumeIsolated {
            let h = try Harness(selfTest: true)
            // Espaçamento de 2 mm entre cortes muda o volume esperado: o autoteste acompanha.
            let viewer = h.addViewer(spacing: 0.5, interval: 2)
            let abc = try XCTUnwrap(try SelfTest.run(in: viewer).first { $0.name == "ABC/2" })
            XCTAssertTrue(abc.passed, abc.line)
            XCTAssertTrue(abc.detail.contains("4,80"), abc.detail)
            // Uma conferência que não bate aparece como FALHOU na linha do registro.
            XCTAssertTrue(SelfTest.Check(name: "x", passed: false, detail: "y").line.contains("FALHOU"))
        }
    }
}
