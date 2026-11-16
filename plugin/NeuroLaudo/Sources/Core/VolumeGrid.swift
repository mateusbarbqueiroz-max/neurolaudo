//  NeuroLaudo — cálculo puro, sem dependência do IsiX nem do AppKit.
//
//  Junta os cortes de uma série em um volume e grava no formato NIfTI-1, que é
//  o que o motor de volumetria lê. O ponto delicado é a orientação: um sinal
//  trocado aqui inverteria direita e esquerda no resultado. Por isso a matriz
//  sai das posições reais dos cortes, e os testes conferem lado por lado.

import Foundation

/// Geometria de um corte, como o DICOM a descreve (milímetros, sistema LPS).
struct SliceGeometry: Equatable, Sendable {
    var columns: Int
    var rows: Int
    /// Distância entre colunas vizinhas (largura do pixel).
    var columnSpacing: Double
    /// Distância entre linhas vizinhas (altura do pixel).
    var rowSpacing: Double
    /// Centro do primeiro pixel (coluna 0, linha 0).
    var position: Vec3
    /// Para onde aponta uma linha da imagem, isto é, o sentido em que a coluna cresce.
    var rowDirection: Vec3
    /// Para onde aponta uma coluna da imagem, isto é, o sentido em que a linha cresce.
    var columnDirection: Vec3
}

enum VolumeGridError: Error, Equatable, LocalizedError {
    case tooFewSlices(Int)
    case sizeMismatch(slice: Int)
    case orientationMismatch(slice: Int)
    case repeatedPosition(slice: Int)
    case unevenSpacing(expected: Double, found: Double)

    var errorDescription: String? {
        switch self {
        case .tooFewSlices(let count):
            return "A série tem \(count) corte(s); a volumetria precisa de uma série volumétrica."
        case .sizeMismatch(let slice):
            return "O corte \(slice + 1) tem tamanho ou espaçamento diferente dos outros."
        case .orientationMismatch(let slice):
            return "O corte \(slice + 1) tem orientação diferente dos outros."
        case .repeatedPosition(let slice):
            return "O corte \(slice + 1) repete a posição de outro: a série parece ter mais de um volume."
        case .unevenSpacing(let expected, let found):
            return "Os cortes não estão igualmente espaçados (\(Fmt.number(expected, decimals: 2)) e "
                + "\(Fmt.number(found, decimals: 2)) mm): falta algum corte na série."
        }
    }
}

/// Um volume montado a partir dos cortes de uma série.
struct VolumeGrid: Equatable, Sendable {
    let columns: Int
    let rows: Int
    let slices: Int
    /// Para cada corte do volume, o índice que ele tinha na série (a série pode vir em qualquer ordem).
    let order: [Int]
    /// Tamanho do voxel em milímetros: entre colunas, entre linhas, entre cortes.
    let spacing: [Double]
    /// Matriz 4×4, por linhas: leva o voxel (coluna, linha, corte) a milímetros no sistema RAS
    /// (+x direita, +y anterior, +z superior), que é o do NIfTI.
    let affine: [[Double]]

    /// Em que sentido cada índice cresce, em letras: R/L (direita/esquerda), A/P, S/I.
    /// Por exemplo "PIR": colunas para posterior, linhas para inferior, cortes para a direita.
    var orientationCode: String {
        (0..<3).map { axis -> String in
            let v = [affine[0][axis], affine[1][axis], affine[2][axis]]
            let main = (0..<3).max { abs(v[$0]) < abs(v[$1]) }!
            let letters = [("R", "L"), ("A", "P"), ("S", "I")][main]
            return v[main] >= 0 ? letters.0 : letters.1
        }.joined()
    }

    static func make(_ slices: [SliceGeometry]) throws -> VolumeGrid {
        guard slices.count >= 2, let first = slices.first else { throw VolumeGridError.tooFewSlices(slices.count) }
        let rowDir = first.rowDirection
        let colDir = first.columnDirection
        let normal = Vec3(x: rowDir.y * colDir.z - rowDir.z * colDir.y,
                          y: rowDir.z * colDir.x - rowDir.x * colDir.z,
                          z: rowDir.x * colDir.y - rowDir.y * colDir.x)
        for (index, slice) in slices.enumerated() {
            guard slice.columns == first.columns, slice.rows == first.rows,
                  abs(slice.columnSpacing - first.columnSpacing) < 1e-3,
                  abs(slice.rowSpacing - first.rowSpacing) < 1e-3 else {
                throw VolumeGridError.sizeMismatch(slice: index)
            }
            guard slice.rowDirection.dot(rowDir) > 0.9999, slice.columnDirection.dot(colDir) > 0.9999 else {
                throw VolumeGridError.orientationMismatch(slice: index)
            }
        }
        // Ordena pela posição ao longo da normal: o índice do corte passa a crescer nesse sentido.
        let along = slices.map { $0.position.dot(normal) }
        let order = slices.indices.sorted { along[$0] < along[$1] }
        let gaps = (1..<order.count).map { along[order[$0]] - along[order[$0 - 1]] }
        // Posição repetida primeiro: é o sinal de série com mais de um volume (por exemplo, duas fases).
        if let repeated = gaps.firstIndex(where: { $0 < 1e-4 }) {
            throw VolumeGridError.repeatedPosition(slice: order[repeated + 1])
        }
        let step = (along[order[order.count - 1]] - along[order[0]]) / Double(slices.count - 1)
        let tolerance = max(0.02, 0.02 * step)
        if let uneven = gaps.first(where: { abs($0 - step) > tolerance }) {
            throw VolumeGridError.unevenSpacing(expected: gaps.min() ?? step, found: uneven)
        }
        let origin = slices[order[0]].position
        let last = slices[order[order.count - 1]].position
        let sliceStep = (last - origin) * (1.0 / Double(slices.count - 1))
        let i = rowDir * first.columnSpacing
        let j = colDir * first.rowSpacing
        // LPS -> RAS: troca o sinal de x e de y.
        let affine: [[Double]] = [
            [-i.x, -j.x, -sliceStep.x, -origin.x],
            [-i.y, -j.y, -sliceStep.y, -origin.y],
            [i.z, j.z, sliceStep.z, origin.z],
            [0, 0, 0, 1],
        ]
        return VolumeGrid(columns: first.columns, rows: first.rows, slices: slices.count, order: order,
                          spacing: [first.columnSpacing, first.rowSpacing, sliceStep.length], affine: affine)
    }

    /// Posição em RAS do centro de um voxel.
    func position(column: Double, row: Double, slice: Double) -> Vec3 {
        let v = [column, row, slice, 1.0]
        let p = (0..<3).map { r in (0..<4).reduce(0.0) { $0 + affine[r][$1] * v[$1] } }
        return Vec3(x: p[0], y: p[1], z: p[2])
    }
}

/// Gravação mínima de NIfTI-1 (um arquivo .nii, valores em ponto flutuante de 32 bits).
enum Nifti {
    static let headerSize = 352

    /// Cabeçalho de 352 bytes. Os valores dos voxels vêm logo depois: colunas, depois linhas, depois cortes.
    static func header(for grid: VolumeGrid) -> [UInt8] {
        var bytes = [UInt8](repeating: 0, count: headerSize)
        func put<T>(_ value: T, at offset: Int) {
            withUnsafeBytes(of: value) { raw in
                for (n, byte) in raw.enumerated() { bytes[offset + n] = byte }
            }
        }
        put(Int32(348).littleEndian, at: 0)                                   // sizeof_hdr
        let dim: [Int16] = [3, Int16(grid.columns), Int16(grid.rows), Int16(grid.slices), 1, 1, 1, 1]
        for (n, value) in dim.enumerated() { put(value.littleEndian, at: 40 + 2 * n) }
        put(Int16(16).littleEndian, at: 70)                                   // datatype: float32
        put(Int16(32).littleEndian, at: 72)                                   // bitpix
        let pixdim: [Float] = [1, Float(grid.spacing[0]), Float(grid.spacing[1]), Float(grid.spacing[2]), 0, 0, 0, 0]
        for (n, value) in pixdim.enumerated() { put(value.bitPattern.littleEndian, at: 76 + 4 * n) }
        put(Float(headerSize).bitPattern.littleEndian, at: 108)               // vox_offset
        put(Float(1).bitPattern.littleEndian, at: 112)                        // scl_slope
        bytes[123] = 2                                                        // xyzt_units: milímetros
        put(Int16(0).littleEndian, at: 252)                                   // qform_code: não usado
        put(Int16(1).littleEndian, at: 254)                                   // sform_code: coordenadas do aparelho
        for row in 0..<3 {
            for column in 0..<4 {
                put(Float(grid.affine[row][column]).bitPattern.littleEndian, at: 280 + 16 * row + 4 * column)
            }
        }
        bytes[344] = UInt8(ascii: "n")
        bytes[345] = UInt8(ascii: "+")
        bytes[346] = UInt8(ascii: "1")
        return bytes
    }

    /// Bytes de um corte (valores em ordem de linha, como no DICOM), prontos para gravar.
    static func bytes(of samples: [Float]) -> Data {
        samples.withUnsafeBufferPointer { buffer in
            #if _endian(little)
            return Data(buffer: buffer)
            #else
            return Data(buffer.flatMap { withUnsafeBytes(of: $0.bitPattern.littleEndian) { Array($0) } })
            #endif
        }
    }
}
