//  NeuroLaudo — cálculo puro, sem dependência do IsiX nem do AppKit.
//  Este arquivo compila e é testado também em Linux (ver plugin/Package.swift).

import Foundation

/// Ponto ou vetor em coordenadas do paciente: milímetros, sistema LPS do DICOM
/// (+x para a esquerda do paciente, +y para trás, +z para cima).
struct Vec3: Equatable, Sendable {
    var x: Double
    var y: Double
    var z: Double

    init(x: Double, y: Double, z: Double) {
        self.x = x
        self.y = y
        self.z = z
    }

    static func + (a: Vec3, b: Vec3) -> Vec3 { Vec3(x: a.x + b.x, y: a.y + b.y, z: a.z + b.z) }
    static func - (a: Vec3, b: Vec3) -> Vec3 { Vec3(x: a.x - b.x, y: a.y - b.y, z: a.z - b.z) }
    static func * (a: Vec3, s: Double) -> Vec3 { Vec3(x: a.x * s, y: a.y * s, z: a.z * s) }

    func dot(_ b: Vec3) -> Double { x * b.x + y * b.y + z * b.z }
    var length: Double { dot(self).squareRoot() }
}

/// Segmento de reta entre dois pontos do paciente: uma medida de comprimento.
struct Segment: Equatable, Sendable {
    var start: Vec3
    var end: Vec3

    var lengthMM: Double { (end - start).length }
}

enum Geometry {
    /// Distância de um ponto a uma reta infinita que passa por `a` e `b`, e o pé
    /// da perpendicular. `nil` se `a` e `b` coincidem.
    static func pointToLine(_ p: Vec3, through a: Vec3, and b: Vec3) -> (distance: Double, foot: Vec3)? {
        let d = b - a
        let dd = d.dot(d)
        guard dd > 1e-12 else { return nil }
        let t = (p - a).dot(d) / dd
        let foot = a + d * t
        return ((p - foot).length, foot)
    }

    /// Ângulo agudo, em graus (0 a 90), entre dois segmentos. `nil` se algum é nulo.
    static func acuteAngle(_ s1: Segment, _ s2: Segment) -> Double? {
        let u = s1.end - s1.start
        let v = s2.end - s2.start
        let lu = u.length, lv = v.length
        guard lu > 1e-9, lv > 1e-9 else { return nil }
        let c = min(1, abs(u.dot(v)) / (lu * lv))
        return acos(c) * 180 / .pi
    }
}

/// Números no formato brasileiro (vírgula decimal).
enum Fmt {
    static func number(_ value: Double, decimals: Int) -> String {
        String(format: "%.\(decimals)f", value).replacingOccurrences(of: ".", with: ",")
    }

    static func mm(_ value: Double) -> String { number(value, decimals: 1) + " mm" }
    static func cm(fromMM value: Double) -> String { number(value / 10, decimals: 1) + " cm" }

    /// Data como no Brasil: 21/11/2026.
    static func date(_ value: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "pt_BR")
        formatter.dateFormat = "dd/MM/yyyy"
        return formatter.string(from: value)
    }
}
