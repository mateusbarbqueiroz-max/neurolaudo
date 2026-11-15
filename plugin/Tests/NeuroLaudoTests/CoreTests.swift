import XCTest
@testable import NeuroLaudo

final class GeometryTests: XCTestCase {
    func testPointToLine() throws {
        let r = try XCTUnwrap(Geometry.pointToLine(Vec3(x: 3, y: 5, z: 0), through: Vec3(x: 0, y: 0, z: 0), and: Vec3(x: 0, y: 10, z: 0)))
        XCTAssertEqual(r.distance, 3, accuracy: 1e-9)
        XCTAssertEqual(r.foot, Vec3(x: 0, y: 5, z: 0))
        XCTAssertNil(Geometry.pointToLine(Vec3(x: 1, y: 1, z: 1), through: Vec3(x: 0, y: 0, z: 0), and: Vec3(x: 0, y: 0, z: 0)))
    }

    func testAcuteAngle() throws {
        let h = Segment(start: Vec3(x: 0, y: 0, z: 0), end: Vec3(x: 10, y: 0, z: 0))
        let v = Segment(start: Vec3(x: 5, y: -4, z: 0), end: Vec3(x: 5, y: 4, z: 0))
        XCTAssertEqual(try XCTUnwrap(Geometry.acuteAngle(h, v)), 90, accuracy: 1e-9)
        let d = Segment(start: Vec3(x: 0, y: 0, z: 0), end: Vec3(x: -3, y: -3, z: 0))
        XCTAssertEqual(try XCTUnwrap(Geometry.acuteAngle(h, d)), 45, accuracy: 1e-9)
    }

    func testBrazilianNumbers() {
        XCTAssertEqual(Fmt.number(0.305, decimals: 2), "0,30")
        XCTAssertEqual(Fmt.mm(6.25), "6,2 mm")
        XCTAssertEqual(Fmt.cm(fromMM: 42), "4,2 cm")
    }
}

final class MeasuresTests: XCTestCase {
    private func line(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) -> Segment {
        Segment(start: Vec3(x: x0, y: y0, z: 0), end: Vec3(x: x1, y: y1, z: 0))
    }

    func testEvans() throws {
        // A ordem das linhas não importa: a menor é a dos cornos frontais.
        let r = try NeuroMeasures.evans(line(0, 0, 120, 0), line(40, 10, 76, 10))
        XCTAssertEqual(r.hornsMM, 36, accuracy: 1e-9)
        XCTAssertEqual(r.skullMM, 120, accuracy: 1e-9)
        XCTAssertEqual(r.index, 0.30, accuracy: 1e-9)
        XCTAssertFalse(r.isEnlarged)
        XCTAssertTrue(try NeuroMeasures.evans(line(0, 0, 120, 0), line(0, 0, 42, 0)).isEnlarged)
        XCTAssertThrowsError(try NeuroMeasures.evans(line(0, 0, 0, 0), line(0, 0, 42, 0)))
    }

    func testEvansSummaryText() throws {
        let text = try NeuroMeasures.evans(line(0, 0, 120, 0), line(0, 0, 42, 0)).summary
        XCTAssertTrue(text.contains("0,35"), text)
        XCTAssertTrue(text.contains("ventriculomegalia"), text)
    }

    func testAbc2() throws {
        XCTAssertEqual(NeuroMeasures.abc2VolumeML(aMM: 40, bMM: 30, cMM: 20), 12, accuracy: 1e-9)
        let r = try NeuroMeasures.hematoma(line(0, 0, 0, 30), line(-20, 15, 20, 15), sliceCount: 4, sliceIntervalMM: 5)
        XCTAssertEqual(r.aMM, 40, accuracy: 1e-9)
        XCTAssertEqual(r.bMM, 30, accuracy: 1e-9)
        XCTAssertEqual(r.cMM, 20, accuracy: 1e-9)
        XCTAssertEqual(r.volumeML, 12, accuracy: 1e-9)
        XCTAssertTrue(r.isRoughlyPerpendicular)
        XCTAssertTrue(r.summary.contains("12,0 mL"), r.summary)
        XCTAssertFalse(r.summary.contains("Atenção"), r.summary)
    }

    func testAbc2WarnsWhenNotPerpendicular() throws {
        let r = try NeuroMeasures.hematoma(line(0, 0, 40, 0), line(0, 0, 30, 5), sliceCount: 2, sliceIntervalMM: 5)
        XCTAssertFalse(r.isRoughlyPerpendicular)
        XCTAssertTrue(r.summary.contains("Atenção"), r.summary)
    }

    func testAbc2RejectsBadInput() {
        XCTAssertThrowsError(try NeuroMeasures.hematoma(line(0, 0, 40, 0), line(0, 0, 0, 30), sliceCount: 0, sliceIntervalMM: 5))
        XCTAssertThrowsError(try NeuroMeasures.hematoma(line(0, 0, 40, 0), line(0, 0, 0, 30), sliceCount: 3, sliceIntervalMM: 0))
    }

    func testMidlineShiftSide() throws {
        // Linha média ao longo de y (anteroposterior). LPS: x positivo = esquerda do paciente.
        let midline = line(0, -80, 0, 90)
        let left = try NeuroMeasures.midlineShift(midline: midline, septum: Vec3(x: 6.2, y: 0, z: 0))
        XCTAssertEqual(left.shiftMM, 6.2, accuracy: 1e-9)
        XCTAssertEqual(left.side, .left)
        let right = try NeuroMeasures.midlineShift(midline: midline, septum: Vec3(x: -4, y: 10, z: 0))
        XCTAssertEqual(right.side, .right)
        XCTAssertTrue(right.summary.contains("4,0 mm para a direita"), right.summary)
        let none = try NeuroMeasures.midlineShift(midline: midline, septum: Vec3(x: 0.1, y: 0, z: 0))
        XCTAssertTrue(none.summary.contains("Sem desvio"), none.summary)
    }

    func testMidlineShiftOnTiltedHead() throws {
        // Cabeça rodada 10°: a distância é medida perpendicular à linha desenhada.
        let a = 10.0 * Double.pi / 180
        let dir = Vec3(x: sin(a), y: cos(a), z: 0), perp = Vec3(x: cos(a), y: -sin(a), z: 0)
        let midline = Segment(start: dir * -80, end: dir * 90)
        let r = try NeuroMeasures.midlineShift(midline: midline, septum: dir * 5 + perp * 7)
        XCTAssertEqual(r.shiftMM, 7, accuracy: 1e-9)
        XCTAssertEqual(r.side, .left)
    }
}

final class AspectsTests: XCTestCase {
    func testScore() throws {
        XCTAssertEqual(Aspects.regions.count, 10)
        XCTAssertEqual(try Aspects.score(affected: []), 10)
        XCTAssertEqual(try Aspects.score(affected: ["C", "M2"]), 8)
        XCTAssertThrowsError(try Aspects.score(affected: ["X"]))
    }

    func testSummary() throws {
        XCTAssertEqual(try Aspects.summary(affected: ["M2", "I"], side: .right),
                       "ASPECTS 8 no território da artéria cerebral média direita (acometimento de: I, M2).")
        XCTAssertTrue(try Aspects.summary(affected: [], side: .left).hasPrefix("ASPECTS 10"))
    }
}
