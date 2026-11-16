import XCTest
@testable import NeuroLaudo

/// Série sagital de teste: colunas para posterior, linhas para inferior. A normal (linha × coluna)
/// aponta para a direita do paciente. `leftToRight`: ordem em que os cortes vêm na série.
private func sagittalSeries(count: Int = 6, gap: Double = 1.2, leftToRight: Bool = true) -> [SliceGeometry] {
    (0..<count).map { n in
        // x em LPS: positivo é esquerda. O primeiro corte fica à esquerda quando leftToRight.
        let x = leftToRight ? 30.0 - gap * Double(n) : 30.0 - gap * Double(count - 1 - n)
        return SliceGeometry(columns: 8, rows: 10, columnSpacing: 0.9, rowSpacing: 1.1,
                             position: Vec3(x: x, y: -40, z: 50),
                             rowDirection: Vec3(x: 0, y: 1, z: 0), columnDirection: Vec3(x: 0, y: 0, z: -1))
    }
}

final class VolumeGridTests: XCTestCase {
    func testSagittalSeriesBecomesAVolumeInScannerCoordinates() throws {
        let grid = try VolumeGrid.make(sagittalSeries())
        XCTAssertEqual([grid.columns, grid.rows, grid.slices], [8, 10, 6])
        XCTAssertEqual(grid.order, [0, 1, 2, 3, 4, 5])
        XCTAssertEqual(grid.spacing[0], 0.9, accuracy: 1e-9)
        XCTAssertEqual(grid.spacing[1], 1.1, accuracy: 1e-9)
        XCTAssertEqual(grid.spacing[2], 1.2, accuracy: 1e-9)
        XCTAssertEqual(grid.orientationCode, "PIR")

        // Primeiro voxel: 30 mm à esquerda (RAS x = -30), 40 mm à frente (y = +40), 50 mm acima.
        let first = grid.position(column: 0, row: 0, slice: 0)
        XCTAssertEqual(first.x, -30, accuracy: 1e-9)
        XCTAssertEqual(first.y, 40, accuracy: 1e-9)
        XCTAssertEqual(first.z, 50, accuracy: 1e-9)
        // Andar nas colunas leva para trás; nas linhas, para baixo; nos cortes, para a direita.
        XCTAssertEqual(grid.position(column: 1, row: 0, slice: 0).y, 40 - 0.9, accuracy: 1e-9)
        XCTAssertEqual(grid.position(column: 0, row: 1, slice: 0).z, 50 - 1.1, accuracy: 1e-9)
        XCTAssertEqual(grid.position(column: 0, row: 0, slice: 5).x, -30 + 5 * 1.2, accuracy: 1e-9)
    }

    func testSliceOrderInTheSeriesDoesNotChangeTheVolume() throws {
        let forward = try VolumeGrid.make(sagittalSeries(leftToRight: true))
        let backward = try VolumeGrid.make(sagittalSeries(leftToRight: false))
        XCTAssertEqual(backward.order, [5, 4, 3, 2, 1, 0])
        XCTAssertEqual(forward.orientationCode, backward.orientationCode)
        for row in 0..<3 {
            for column in 0..<4 {
                XCTAssertEqual(forward.affine[row][column], backward.affine[row][column], accuracy: 1e-9)
            }
        }
    }

    func testAxialSeriesKeepsPatientLeftOnTheLeft() throws {
        // Axial comum: colunas para a esquerda do paciente, linhas para trás, cortes subindo.
        let slices = (0..<4).map { n in
            SliceGeometry(columns: 4, rows: 4, columnSpacing: 1, rowSpacing: 1,
                          position: Vec3(x: -100, y: -120, z: 10 + 5 * Double(n)),
                          rowDirection: Vec3(x: 1, y: 0, z: 0), columnDirection: Vec3(x: 0, y: 1, z: 0))
        }
        let grid = try VolumeGrid.make(slices)
        XCTAssertEqual(grid.orientationCode, "LPS")
        XCTAssertEqual(grid.spacing[2], 5, accuracy: 1e-9)
        // A coluna 0 começa 100 mm à direita do paciente: em RAS, x = +100.
        XCTAssertEqual(grid.position(column: 0, row: 0, slice: 0).x, 100, accuracy: 1e-9)
        XCTAssertEqual(grid.position(column: 3, row: 0, slice: 0).x, 97, accuracy: 1e-9)
    }

    func testProblemsInTheSeriesAreRefused() {
        XCTAssertThrowsError(try VolumeGrid.make([sagittalSeries()[0]])) {
            XCTAssertEqual($0 as? VolumeGridError, .tooFewSlices(1))
        }
        var missing = sagittalSeries()
        missing.remove(at: 2)
        XCTAssertThrowsError(try VolumeGrid.make(missing)) { error in
            guard case .unevenSpacing = error as? VolumeGridError else { return XCTFail("\(error)") }
        }
        var repeated = sagittalSeries()
        repeated.append(repeated[1])
        XCTAssertThrowsError(try VolumeGrid.make(repeated)) { error in
            guard case .repeatedPosition = error as? VolumeGridError else { return XCTFail("\(error)") }
        }
        var tilted = sagittalSeries()
        tilted[3].rowDirection = Vec3(x: 0, y: 0.8, z: 0.6)
        XCTAssertThrowsError(try VolumeGrid.make(tilted)) {
            XCTAssertEqual($0 as? VolumeGridError, .orientationMismatch(slice: 3))
        }
        var resized = sagittalSeries()
        resized[4].rows = 12
        XCTAssertThrowsError(try VolumeGrid.make(resized)) {
            XCTAssertEqual($0 as? VolumeGridError, .sizeMismatch(slice: 4))
        }
    }

    func testNiftiHeaderFields() throws {
        let grid = try VolumeGrid.make(sagittalSeries())
        let header = Nifti.header(for: grid)
        XCTAssertEqual(header.count, 352)
        func int16(_ offset: Int) -> Int16 { Int16(littleEndian: header[offset..<offset + 2].withUnsafeBytes { $0.loadUnaligned(as: Int16.self) }) }
        func float(_ offset: Int) -> Float {
            Float(bitPattern: UInt32(littleEndian: header[offset..<offset + 4].withUnsafeBytes { $0.loadUnaligned(as: UInt32.self) }))
        }
        XCTAssertEqual(Array(header[0..<4]), [92, 1, 0, 0])              // 348
        XCTAssertEqual([int16(40), int16(42), int16(44), int16(46)], [3, 8, 10, 6])
        XCTAssertEqual([int16(70), int16(72)], [16, 32])                 // float32
        XCTAssertEqual(float(80), 0.9, accuracy: 1e-6)
        XCTAssertEqual(float(84), 1.1, accuracy: 1e-6)
        XCTAssertEqual(float(88), 1.2, accuracy: 1e-6)
        XCTAssertEqual(float(108), 352)
        XCTAssertEqual([int16(252), int16(254)], [0, 1])
        XCTAssertEqual(float(280 + 12), -30)                             // srow_x: origem em x
        XCTAssertEqual(float(296), -0.9, accuracy: 1e-6)                 // srow_y: colunas para posterior
        XCTAssertEqual(float(312 + 4), -1.1, accuracy: 1e-6)             // srow_z: linhas para inferior
        XCTAssertEqual(float(280 + 8), 1.2, accuracy: 1e-6)              // srow_x: cortes para a direita
        XCTAssertEqual(Array(header[344..<348]), [110, 43, 49, 0])       // "n+1"
        XCTAssertEqual(Nifti.bytes(of: [1.0, -2.5]).count, 8)
        XCTAssertEqual(Array(Nifti.bytes(of: [1.0])), [0, 0, 128, 63])
    }

    /// Para a conferência cruzada com o motor em Python (ver .github/workflows/testes.yml): com a variável
    /// NEUROLAUDO_NIFTI_TESTE, grava um volume cujo valor em cada voxel é coluna + 10·linha + 100·corte.
    func testWriteSampleVolumeForTheEngine() throws {
        guard let path = ProcessInfo.processInfo.environment["NEUROLAUDO_NIFTI_TESTE"] else { return }
        let grid = try VolumeGrid.make(sagittalSeries())
        var data = Data(Nifti.header(for: grid))
        for slice in 0..<grid.slices {
            var samples: [Float] = []
            for row in 0..<grid.rows {
                for column in 0..<grid.columns {
                    samples.append(Float(column + 10 * row + 100 * slice))
                }
            }
            data.append(Nifti.bytes(of: samples))
        }
        try data.write(to: URL(fileURLWithPath: path))
    }
}
