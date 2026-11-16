//  IMITAÇÃO do IsiXPluginKit, só para conferir e testar o complemento em Linux.
//
//  O IsiXPluginKit de verdade é um framework de macOS (plugin/SDK). Este arquivo
//  repete, à mão, as assinaturas públicas que o NeuroLaudo usa, copiadas de
//  SDK/IsiXPluginKit.framework/.../arm64-apple-macos.swiftinterface (kit 1.0.0),
//  com um comportamento em memória para os testes. NÃO entra no complemento.
//
//  Tudo o que só existe aqui (e não no kit de verdade) tem "stub" no nome:
//  o código do complemento nunca pode usar esses membros.

import Foundation

// MARK: - Substitutos de tipos do AppKit (só Linux)

public final class NSWindow: @unchecked Sendable {
    public init() {}
}

public enum NSEvent {
    public struct ModifierFlags: OptionSet, Sendable {
        public let rawValue: UInt
        public init(rawValue: UInt) { self.rawValue = rawValue }
        public static let shift = ModifierFlags(rawValue: 1 << 17)
        public static let control = ModifierFlags(rawValue: 1 << 18)
        public static let option = ModifierFlags(rawValue: 1 << 19)
        public static let command = ModifierFlags(rawValue: 1 << 20)
    }
}

// MARK: - Comandos

public struct IsiXCommand: Hashable, Sendable {
    public enum Placement: Hashable, Sendable {
        case imageFilters
        case roiTools
        case database
        case other
    }

    public enum Requirement: Hashable, Sendable {
        case none
        case viewer
    }

    public var id: String
    public var title: String
    public var placement: Placement
    public var requirement: Requirement

    public init(id: String, title: String, placement: Placement = .other, requirement: Requirement = .none) {
        self.id = id
        self.title = title
        self.placement = placement
        self.requirement = requirement
    }
}

@MainActor public final class IsiXCommandInvocation {
    public let command: IsiXCommand
    public let viewer: IsiXViewer?
    public let parentWindow: NSWindow?

    public init(stubCommand: IsiXCommand, viewer: IsiXViewer?, parentWindow: NSWindow? = nil) {
        self.command = stubCommand
        self.viewer = viewer
        self.parentWindow = parentWindow
    }
}

// MARK: - Geometria e imagem

public struct IsiXVector3: Hashable, Sendable {
    public var x: Double
    public var y: Double
    public var z: Double

    public init(x: Double, y: Double, z: Double) {
        self.x = x
        self.y = y
        self.z = z
    }

    public static func + (a: IsiXVector3, b: IsiXVector3) -> IsiXVector3 { IsiXVector3(x: a.x + b.x, y: a.y + b.y, z: a.z + b.z) }
    public static func - (a: IsiXVector3, b: IsiXVector3) -> IsiXVector3 { IsiXVector3(x: a.x - b.x, y: a.y - b.y, z: a.z - b.z) }
    public static func * (a: IsiXVector3, s: Double) -> IsiXVector3 { IsiXVector3(x: a.x * s, y: a.y * s, z: a.z * s) }
    public func dot(_ b: IsiXVector3) -> Double { x * b.x + y * b.y + z * b.z }
    public func cross(_ b: IsiXVector3) -> IsiXVector3 {
        IsiXVector3(x: y * b.z - z * b.y, y: z * b.x - x * b.z, z: x * b.y - y * b.x)
    }
    public var length: Double { dot(self).squareRoot() }
}

public struct IsiXPixelPoint: Hashable, Sendable {
    public var x: Double
    public var y: Double

    public init(x: Double, y: Double) {
        self.x = x
        self.y = y
    }
}

public struct IsiXImageGeometry: Hashable, Sendable {
    public var columns: Int
    public var rows: Int
    public var columnSpacing: Double
    public var rowSpacing: Double
    public var imagePosition: IsiXVector3
    public var rowDirection: IsiXVector3
    public var columnDirection: IsiXVector3
    public var sliceThickness: Double
    public var sliceInterval: Double
    public var sliceLocation: Double

    public init(columns: Int, rows: Int, columnSpacing: Double, rowSpacing: Double, imagePosition: IsiXVector3,
                rowDirection: IsiXVector3, columnDirection: IsiXVector3, sliceThickness: Double, sliceInterval: Double,
                sliceLocation: Double) {
        self.columns = columns
        self.rows = rows
        self.columnSpacing = columnSpacing
        self.rowSpacing = rowSpacing
        self.imagePosition = imagePosition
        self.rowDirection = rowDirection
        self.columnDirection = columnDirection
        self.sliceThickness = sliceThickness
        self.sliceInterval = sliceInterval
        self.sliceLocation = sliceLocation
    }

    public var normal: IsiXVector3 { rowDirection.cross(columnDirection) }

    public func patientPoint(of point: IsiXPixelPoint) -> IsiXVector3 {
        imagePosition + rowDirection * (point.x * columnSpacing) + columnDirection * (point.y * rowSpacing)
    }

    public func pixelPoint(of point: IsiXVector3) -> IsiXPixelPoint {
        let d = point - imagePosition
        return IsiXPixelPoint(x: d.dot(rowDirection) / columnSpacing, y: d.dot(columnDirection) / rowSpacing)
    }
}

public struct IsiXImageAttributes: Hashable, Sendable {
    public var modality: String?
    public var studyInstanceUID: String?
    public var seriesInstanceUID: String?
    public var sopInstanceUID: String?
    public var echoTime: Double?
    public var repetitionTime: Double?
    public var acquisitionDate: Date?
    public var rescaleSlope: Double
    public var rescaleIntercept: Double
    public var isSUV: Bool

    public init(modality: String? = nil, studyInstanceUID: String? = nil, seriesInstanceUID: String? = nil,
                sopInstanceUID: String? = nil, echoTime: Double? = nil, repetitionTime: Double? = nil,
                acquisitionDate: Date? = nil, rescaleSlope: Double = 1, rescaleIntercept: Double = 0, isSUV: Bool = false) {
        self.modality = modality
        self.studyInstanceUID = studyInstanceUID
        self.seriesInstanceUID = seriesInstanceUID
        self.sopInstanceUID = sopInstanceUID
        self.echoTime = echoTime
        self.repetitionTime = repetitionTime
        self.acquisitionDate = acquisitionDate
        self.rescaleSlope = rescaleSlope
        self.rescaleIntercept = rescaleIntercept
        self.isSUV = isSUV
    }
}

// MARK: - Pixels e imagens

public struct IsiXPixelBuffer<Sample>: Sendable, Equatable where Sample: Equatable, Sample: Sendable {
    public let width: Int
    public let height: Int
    public let channels: Int
    public private(set) var samples: [Sample]

    public init(width: Int, height: Int, channels: Int = 1, samples: [Sample]) throws {
        guard width > 0, height > 0, channels > 0, samples.count == width * height * channels else {
            throw IsiXPluginError.dimensionMismatch
        }
        self.width = width
        self.height = height
        self.channels = channels
        self.samples = samples
    }

    public subscript(column: Int, row: Int, channel: Int = 0) -> Sample {
        get { samples[(row * width + column) * channels + channel] }
        set { samples[(row * width + column) * channels + channel] = newValue }
    }
}

public enum IsiXPixelData: Sendable, Equatable {
    case float32(IsiXPixelBuffer<Float>)
    case rgba8(IsiXPixelBuffer<UInt8>)
}

public struct IsiXImageVersion: Hashable, Sendable {
    public let viewer: IsiXViewerID
    public let slice: Int
    public let phase: Int
}

public struct IsiXImage: Sendable {
    public let version: IsiXImageVersion
    public let geometry: IsiXImageGeometry
    public let attributes: IsiXImageAttributes
    public let pixels: IsiXPixelData

    public var viewerID: IsiXViewerID { version.viewer }
    public var slice: Int { version.slice }
    public var phase: Int { version.phase }
    public var scalarPixels: IsiXPixelBuffer<Float>? {
        if case .float32(let buffer) = pixels { return buffer }
        return nil
    }
}

public struct IsiXWindowLevel: Hashable, Sendable {
    public var center: Double
    public var width: Double

    public init(center: Double, width: Double) {
        self.center = center
        self.width = width
    }
}

public struct IsiXSeriesSummary: Hashable, Sendable {
    public var sliceCount: Int
    public var phaseCount: Int
    public var currentSlice: Int
    public var currentPhase: Int
    public var studyInstanceUID: String?
    public var seriesInstanceUID: String?
    public var seriesDescription: String?
    public var modality: String?

    public init(stubSliceCount: Int, currentSlice: Int = 0, studyInstanceUID: String?, seriesInstanceUID: String?,
                seriesDescription: String?, modality: String?) {
        self.sliceCount = stubSliceCount
        self.phaseCount = 1
        self.currentSlice = currentSlice
        self.currentPhase = 0
        self.studyInstanceUID = studyInstanceUID
        self.seriesInstanceUID = seriesInstanceUID
        self.seriesDescription = seriesDescription
        self.modality = modality
    }
}

public struct IsiXViewerID: Hashable, Sendable, CustomStringConvertible {
    public let rawValue: UUID
    public var description: String { rawValue.uuidString }

    public init(stubRawValue: UUID = UUID()) { rawValue = stubRawValue }
}

public struct IsiXSlicePosition: Hashable, Sendable {
    public var slice: Int
    public var phase: Int

    public init(slice: Int, phase: Int) {
        self.slice = slice
        self.phase = phase
    }
}

// MARK: - ROIs

public struct IsiXROIID: Hashable, Sendable, CustomStringConvertible {
    public let rawValue: UUID
    public var description: String { rawValue.uuidString }

    public init(stubRawValue: UUID = UUID()) { rawValue = stubRawValue }
}

public enum IsiXROIKind: Hashable, Sendable {
    case point
    case line
    case rectangle
    case oval
    case polygon
    case polyline
    case angle
    case text
    case brush
    case other
}

public struct IsiXROI: Hashable, Sendable {
    public var id: IsiXROIID
    public var kind: IsiXROIKind
    public var name: String
    public var comment: String
    public var slice: Int
    public var phase: Int
    public var points: [IsiXPixelPoint]
    public var patientPoints: [IsiXVector3]
    public var isSelected: Bool
    public var showsTextBox: Bool

    public init(stubKind: IsiXROIKind, name: String, slice: Int, points: [IsiXPixelPoint], patientPoints: [IsiXVector3],
                isSelected: Bool = false) {
        self.id = IsiXROIID()
        self.kind = stubKind
        self.name = name
        self.comment = ""
        self.slice = slice
        self.phase = 0
        self.points = points
        self.patientPoints = patientPoints
        self.isSelected = isSelected
        self.showsTextBox = true
    }
}

public struct IsiXROIUpdate: Hashable, Sendable {
    public var points: [IsiXPixelPoint]?
    public var kind: IsiXROIKind?
    public var name: String?
    public var comment: String?
    public var isSelected: Bool?
    public var showsTextBox: Bool?

    public init(points: [IsiXPixelPoint]? = nil, kind: IsiXROIKind? = nil, name: String? = nil, comment: String? = nil,
                isSelected: Bool? = nil, showsTextBox: Bool? = nil) {
        self.points = points
        self.kind = kind
        self.name = name
        self.comment = comment
        self.isSelected = isSelected
        self.showsTextBox = showsTextBox
    }
}

public struct IsiXROIDraft: Hashable, Sendable {
    public var kind: IsiXROIKind
    public var points: [IsiXPixelPoint]
    public var name: String?
    public var slice: Int?
    public var phase: Int?

    public init(kind: IsiXROIKind, points: [IsiXPixelPoint], name: String? = nil, slice: Int? = nil, phase: Int? = nil) {
        self.kind = kind
        self.points = points
        self.name = name
        self.slice = slice
        self.phase = phase
    }
}

public struct IsiXROIStatistics: Hashable, Sendable {
    public var mean: Double
    public var standardDeviation: Double
    public var minimum: Double
    public var maximum: Double
    public var sum: Double
    public var area: Double?
    public var length: Double?
}

// MARK: - Erros

public struct IsiXCapability: RawRepresentable, Hashable, Sendable, CustomStringConvertible {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }
    public var description: String { rawValue }

    public static let viewerRead = IsiXCapability(rawValue: "viewer.read")
    public static let viewerWrite = IsiXCapability(rawValue: "viewer.write")
    public static let roi = IsiXCapability(rawValue: "roi")
    public static let databaseRead = IsiXCapability(rawValue: "database.read")
    public static let databaseImport = IsiXCapability(rawValue: "database.import")
    public static let databaseWrite = IsiXCapability(rawValue: "database.write")
    public static let networkSend = IsiXCapability(rawValue: "network.send")
    public static let networkQuery = IsiXCapability(rawValue: "network.query")
    public static let xmlRPC = IsiXCapability(rawValue: "xmlrpc")
}

public enum IsiXPluginError: Error, Sendable, Equatable {
    case viewerClosed
    case capabilityNotDeclared(IsiXCapability)
    case pluginInactive
    case sliceOutOfRange(Int)
    case phaseOutOfRange(Int)
    case staleImage
    case dimensionMismatch
    case roiNotFound
    case unsupportedROIKind(IsiXROIKind)
    case invalidROI(String)
    case invalidCommand(String)
    case commandAlreadyRegistered(String)
    case noDatabase
    case hostFailure(String)
    case notFound(String)
    case invalidValue(String)
    case nodeNotConfigured(String)
    case networkFailure(String)
}

extension IsiXPluginError: LocalizedError {
    public var errorDescription: String? { "IsiXPluginError: \(self)" }
}

// MARK: - Eventos e entrada

public enum IsiXROIChange: Hashable, Sendable {
    case added, modified, removed, selected
}

public struct IsiXDatabaseImage: Hashable, Sendable {
    public var sopInstanceUID: String
    public var seriesInstanceUID: String
    public var studyInstanceUID: String
    public var instanceNumber: Int?
    public var frame: Int
    public var numberOfFrames: Int
    public var file: URL?
    public var modality: String?
    public var columns: Int
    public var rows: Int

    public init(stubSOP: String, series: String, study: String, modality: String? = nil) {
        sopInstanceUID = stubSOP
        seriesInstanceUID = series
        studyInstanceUID = study
        instanceNumber = nil
        frame = 0
        numberOfFrames = 1
        file = nil
        self.modality = modality
        columns = 256
        rows = 256
    }
}

public struct IsiXImagesAdded: Hashable, Sendable {
    public var images: [IsiXDatabaseImage]
    public var sopInstanceUIDsByCallingAETitle: [String: [String]]
    public var isComplete: Bool

    public init(stubImages: [IsiXDatabaseImage], byCallingAETitle: [String: [String]] = [:], isComplete: Bool) {
        images = stubImages
        sopInstanceUIDsByCallingAETitle = byCallingAETitle
        self.isComplete = isComplete
    }
}

public enum IsiXEvent: Hashable, Sendable {
    case viewerOpened(IsiXViewerID)
    case viewerWillClose(IsiXViewerID)
    case sliceChanged(IsiXViewerID, IsiXSlicePosition)
    case roiChanged(IsiXViewerID, IsiXROIID, IsiXROIChange)
    case imagesAdded(IsiXImagesAdded)
}

public struct IsiXEventKinds: OptionSet, Hashable, Sendable {
    public let rawValue: UInt32
    public init(rawValue: UInt32) { self.rawValue = rawValue }
    public static let viewerOpened = IsiXEventKinds(rawValue: 1 << 0)
    public static let viewerWillClose = IsiXEventKinds(rawValue: 1 << 1)
    public static let sliceChanged = IsiXEventKinds(rawValue: 1 << 2)
    public static let roiChanged = IsiXEventKinds(rawValue: 1 << 3)
    public static let imagesAdded = IsiXEventKinds(rawValue: 1 << 4)
    public static let all: IsiXEventKinds = [.viewerOpened, .viewerWillClose, .sliceChanged, .roiChanged, .imagesAdded]
}

public final class IsiXObservation: @unchecked Sendable {
    private var active = true
    public var isActive: Bool { active }
    public func invalidate() { active = false }
    public init(stub: Void = ()) {}
}

public struct IsiXViewerInput: Sendable {
    public enum Kind: Hashable, Sendable {
        case mouseDown
        case mouseDragged
        case mouseUp
        case keyDown
    }

    public let kind: Kind
    public let viewerID: IsiXViewerID
    public let position: IsiXSlicePosition
    public let location: IsiXPixelPoint
    public let locationInWindow: CGPoint
    public let windowNumber: Int
    public let modifierFlags: NSEvent.ModifierFlags
    public let timestamp: TimeInterval
    public let clickCount: Int
    public let characters: String?
    public let keyCode: UInt16?

    public init(kind: Kind, viewerID: IsiXViewerID, position: IsiXSlicePosition, location: IsiXPixelPoint,
                locationInWindow: CGPoint = .zero, windowNumber: Int = 0, modifierFlags: NSEvent.ModifierFlags = [],
                timestamp: TimeInterval = 0, clickCount: Int = 0, characters: String? = nil, keyCode: UInt16? = nil) {
        self.kind = kind
        self.viewerID = viewerID
        self.position = position
        self.location = location
        self.locationInWindow = locationInWindow
        self.windowNumber = windowNumber
        self.modifierFlags = modifierFlags
        self.timestamp = timestamp
        self.clickCount = clickCount
        self.characters = characters
        self.keyCode = keyCode
    }
}

public struct IsiXInputKinds: OptionSet, Hashable, Sendable {
    public let rawValue: UInt32
    public init(rawValue: UInt32) { self.rawValue = rawValue }
    public static let mouseDown = IsiXInputKinds(rawValue: 1 << 0)
    public static let mouseDragged = IsiXInputKinds(rawValue: 1 << 1)
    public static let mouseUp = IsiXInputKinds(rawValue: 1 << 2)
    public static let keyDown = IsiXInputKinds(rawValue: 1 << 3)
    public static let all: IsiXInputKinds = [.mouseDown, .mouseDragged, .mouseUp, .keyDown]
}

// MARK: - Visualizador

@MainActor public final class IsiXViewer {
    public nonisolated let id: IsiXViewerID

    // Estado em memória, só do stub.
    public var stubSeries: IsiXSeriesSummary
    public var stubGeometry: IsiXImageGeometry
    public var stubROIs: [IsiXROI] = []
    public var stubWindowLevel = IsiXWindowLevel(center: 40, width: 400)
    public var stubIsOpen = true
    /// Cortes com geometria e pixels próprios (só do stub). Vazio: todos os cortes usam `stubGeometry`.
    public var stubSlices: [(geometry: IsiXImageGeometry, pixels: IsiXPixelData)] = []

    public init(stubSeries: IsiXSeriesSummary, geometry: IsiXImageGeometry) {
        self.id = IsiXViewerID()
        self.stubSeries = stubSeries
        self.stubGeometry = geometry
    }

    public var isOpen: Bool { stubIsOpen }

    private func checkOpen() throws {
        guard stubIsOpen else { throw IsiXPluginError.viewerClosed }
    }

    public func series() throws -> IsiXSeriesSummary {
        try checkOpen()
        return stubSeries
    }

    public func currentPosition() throws -> IsiXSlicePosition {
        try checkOpen()
        return IsiXSlicePosition(slice: stubSeries.currentSlice, phase: stubSeries.currentPhase)
    }

    public func setCurrentSlice(_ slice: Int) throws {
        try checkOpen()
        guard slice >= 0, slice < stubSeries.sliceCount else { throw IsiXPluginError.sliceOutOfRange(slice) }
        stubSeries.currentSlice = slice
    }

    private func checked(_ slice: Int?) throws -> Int {
        try checkOpen()
        let index = slice ?? stubSeries.currentSlice
        guard index >= 0, index < stubSeries.sliceCount else { throw IsiXPluginError.sliceOutOfRange(index) }
        return index
    }

    public func geometry(slice: Int? = nil, phase: Int? = nil) throws -> IsiXImageGeometry {
        let index = try checked(slice)
        return index < stubSlices.count ? stubSlices[index].geometry : stubGeometry
    }

    public func attributes(slice: Int? = nil, phase: Int? = nil) throws -> IsiXImageAttributes {
        let index = try checked(slice)
        return IsiXImageAttributes(modality: stubSeries.modality, studyInstanceUID: stubSeries.studyInstanceUID,
                                   seriesInstanceUID: stubSeries.seriesInstanceUID,
                                   sopInstanceUID: "\(stubSeries.seriesInstanceUID ?? "1.2.3").\(index + 1)")
    }

    public func image(slice: Int? = nil, phase: Int? = nil) throws -> IsiXImage {
        let index = try checked(slice)
        let geometry = try self.geometry(slice: index)
        let pixels: IsiXPixelData
        if index < stubSlices.count {
            pixels = stubSlices[index].pixels
        } else {
            pixels = .float32(try IsiXPixelBuffer(width: geometry.columns, height: geometry.rows,
                                                  samples: [Float](repeating: 0, count: geometry.columns * geometry.rows)))
        }
        return IsiXImage(version: IsiXImageVersion(viewer: id, slice: index, phase: 0), geometry: geometry,
                         attributes: try attributes(slice: index), pixels: pixels)
    }

    public func windowLevel() throws -> IsiXWindowLevel {
        try checkOpen()
        return stubWindowLevel
    }

    public func setWindowLevel(_ windowLevel: IsiXWindowLevel) throws {
        try checkOpen()
        stubWindowLevel = windowLevel
    }

    public func rois(slice: Int? = nil, phase: Int? = nil) throws -> [IsiXROI] {
        try checkOpen()
        let wanted = slice ?? stubSeries.currentSlice
        return stubROIs.filter { $0.slice == wanted }
    }

    public func addROI(_ draft: IsiXROIDraft) throws -> IsiXROI {
        try checkOpen()
        let roi = IsiXROI(stubKind: draft.kind, name: draft.name ?? "", slice: draft.slice ?? stubSeries.currentSlice,
                          points: draft.points, patientPoints: draft.points.map(stubGeometry.patientPoint(of:)))
        stubROIs.append(roi)
        return roi
    }

    public func removeROI(_ id: IsiXROIID) throws {
        try checkOpen()
        guard let index = stubROIs.firstIndex(where: { $0.id == id }) else { throw IsiXPluginError.roiNotFound }
        stubROIs.remove(at: index)
    }

    @discardableResult
    public func updateROI(_ id: IsiXROIID, _ update: IsiXROIUpdate) throws -> IsiXROI {
        try checkOpen()
        guard let index = stubROIs.firstIndex(where: { $0.id == id }) else { throw IsiXPluginError.roiNotFound }
        if let name = update.name { stubROIs[index].name = name }
        if let comment = update.comment { stubROIs[index].comment = comment }
        if let selected = update.isSelected { stubROIs[index].isSelected = selected }
        return stubROIs[index]
    }

    /// Na imitação só o comprimento de linhas é calculado.
    public func statistics(of id: IsiXROIID) throws -> IsiXROIStatistics {
        try checkOpen()
        guard let roi = stubROIs.first(where: { $0.id == id }) else { throw IsiXPluginError.roiNotFound }
        var length: Double?
        if roi.kind == .line, let first = roi.patientPoints.first, let last = roi.patientPoints.last {
            length = (last - first).length
        }
        return IsiXROIStatistics(mean: 0, standardDeviation: 0, minimum: 0, maximum: 0, sum: 0, area: nil, length: length)
    }

    public func setNeedsDisplay() {}
}

// MARK: - Banco de dados

public struct IsiXStudy: Hashable, Sendable {
    public var studyInstanceUID: String
    public var patientID: String?
    public var patientName: String?
    public var studyDescription: String?
    public var studyDate: Date?
    public var modalities: [String]
    public var seriesCount: Int
    public var accessionNumber: String?
    public var patientBirthDate: Date?
    public var patientSex: String?

    public init(stubUID: String, patientID: String?, studyDescription: String? = nil, studyDate: Date?, modalities: [String]) {
        self.studyInstanceUID = stubUID
        self.patientID = patientID
        self.patientName = nil
        self.studyDescription = studyDescription
        self.studyDate = studyDate
        self.modalities = modalities
        self.seriesCount = 0
        self.accessionNumber = nil
    }
}

public struct IsiXSeries: Hashable, Sendable {
    public var seriesInstanceUID: String
    public var studyInstanceUID: String
    public var seriesDescription: String?
    public var modality: String?
    public var seriesNumber: Int?
    public var imageCount: Int

    public init(stubUID: String, studyUID: String, description: String?, modality: String?, number: Int? = nil, imageCount: Int) {
        self.seriesInstanceUID = stubUID
        self.studyInstanceUID = studyUID
        self.seriesDescription = description
        self.modality = modality
        self.seriesNumber = number
        self.imageCount = imageCount
    }
}

public struct IsiXDatabaseSelection: Hashable, Sendable {
    public var studies: [IsiXStudy]
    public var series: [IsiXSeries]

    public init(stubStudies: [IsiXStudy] = [], series: [IsiXSeries] = []) {
        self.studies = stubStudies
        self.series = series
    }
}

public struct IsiXStudyQuery: Hashable, Sendable {
    public var studyInstanceUID: String?
    public var patientID: String?
    public var patientName: String?
    public var accessionNumber: String?
    public var studyDescription: String?
    public var modality: String?
    public var comment: String?
    public var studyDateFrom: Date?
    public var studyDateTo: Date?
    public var state: Int?
    public var limit: Int?

    public init(studyInstanceUID: String? = nil, patientID: String? = nil, patientName: String? = nil,
                accessionNumber: String? = nil, studyDescription: String? = nil, modality: String? = nil,
                comment: String? = nil, studyDateFrom: Date? = nil, studyDateTo: Date? = nil, state: Int? = nil,
                limit: Int? = nil) {
        self.studyInstanceUID = studyInstanceUID
        self.patientID = patientID
        self.patientName = patientName
        self.accessionNumber = accessionNumber
        self.studyDescription = studyDescription
        self.modality = modality
        self.comment = comment
        self.studyDateFrom = studyDateFrom
        self.studyDateTo = studyDateTo
        self.state = state
        self.limit = limit
    }
}

@MainActor public final class IsiXDatabase {
    public var stubStudies: [IsiXStudy] = []
    public var stubSeries: [IsiXSeries] = []
    public var stubSelection = IsiXDatabaseSelection()
    /// As séries abertas por `openViewer(forSeries:)`, na ordem.
    public var stubOpened: [String] = []
    /// Os pedidos feitos a `writeDerivedSeries`, com os arquivos devolvidos.
    public var stubWritten: [(request: IsiXDerivedSeriesRequest, files: [URL])] = []
    weak var stubContext: IsiXPluginContext?

    public init(stub: Void = ()) {}

    public func selection() throws -> IsiXDatabaseSelection { stubSelection }

    public func selectedStudies() throws -> [IsiXStudy] { stubSelection.studies }

    public func studies(matching query: IsiXStudyQuery) throws -> [IsiXStudy] {
        stubStudies.filter { study in
            if let uid = query.studyInstanceUID, study.studyInstanceUID != uid { return false }
            if let patient = query.patientID, study.patientID != patient { return false }
            return true
        }
    }

    public func study(withInstanceUID uid: String) throws -> IsiXStudy? {
        stubStudies.first { $0.studyInstanceUID == uid }
    }

    public func series(inStudy studyInstanceUID: String) throws -> [IsiXSeries] {
        stubSeries.filter { $0.studyInstanceUID == studyInstanceUID }
    }

    public func series(withInstanceUID uid: String) throws -> IsiXSeries? {
        stubSeries.first { $0.seriesInstanceUID == uid }
    }

    @discardableResult
    public func openViewer(forSeries seriesInstanceUID: String) throws -> IsiXViewer? {
        guard let series = stubSeries.first(where: { $0.seriesInstanceUID == seriesInstanceUID }) else {
            throw IsiXPluginError.notFound(seriesInstanceUID)
        }
        stubOpened.append(seriesInstanceUID)
        let geometry = IsiXImageGeometry(columns: 256, rows: 256, columnSpacing: 1, rowSpacing: 1,
                                         imagePosition: IsiXVector3(x: 0, y: 0, z: 0),
                                         rowDirection: IsiXVector3(x: 1, y: 0, z: 0),
                                         columnDirection: IsiXVector3(x: 0, y: 1, z: 0),
                                         sliceThickness: 1, sliceInterval: 1, sliceLocation: 0)
        let viewer = IsiXViewer(stubSeries: IsiXSeriesSummary(stubSliceCount: max(series.imageCount, 1),
                                                              studyInstanceUID: series.studyInstanceUID,
                                                              seriesInstanceUID: series.seriesInstanceUID,
                                                              seriesDescription: series.seriesDescription,
                                                              modality: series.modality),
                                geometry: geometry)
        stubContext?.stubViewers.append(viewer)
        return viewer
    }
}

public struct IsiXDerivedSeriesRequest: Sendable, Equatable {
    public var studyInstanceUID: String
    public var seriesDescription: String
    public var images: [IsiXPixelData]
    public var sourceSOPInstanceUID: String?
    public var seriesInstanceUID: String?
    public var seriesNumber: Int?
    public var firstInstanceNumber: Int = 1
    public var geometries: [IsiXImageGeometry]?
    public var windowLevel: IsiXWindowLevel?

    public init(studyInstanceUID: String, seriesDescription: String, images: [IsiXPixelData]) {
        self.studyInstanceUID = studyInstanceUID
        self.seriesDescription = seriesDescription
        self.images = images
    }
}

public struct IsiXImportResult: Hashable, Sendable {
    public struct Failure: Hashable, Sendable {
        public var file: URL
        public var reason: String
    }

    public var importedFiles: [URL]
    public var studyInstanceUIDs: [String]
    public var seriesInstanceUIDs: [String]
    public var failures: [Failure]
}

extension IsiXDatabase {
    /// Grava as imagens como arquivos (aqui, arquivos vazios em uma pasta temporária) e guarda o pedido em `stubWritten`.
    public func writeDerivedSeries(_ request: IsiXDerivedSeriesRequest) throws -> [URL] {
        guard !request.images.isEmpty else { throw IsiXPluginError.hostFailure("no images") }
        if let geometries = request.geometries, geometries.count != request.images.count {
            throw IsiXPluginError.dimensionMismatch
        }
        guard stubStudies.contains(where: { $0.studyInstanceUID == request.studyInstanceUID }) else {
            throw IsiXPluginError.notFound(request.studyInstanceUID)
        }
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("isix-stub-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        var files: [URL] = []
        for index in request.images.indices {
            let file = folder.appendingPathComponent("\(index + 1).dcm")
            try Data().write(to: file)
            files.append(file)
        }
        stubWritten.append((request: request, files: files))
        return files
    }

    /// Acrescenta ao banco uma série para cada pedido cujos arquivos estejam na lista.
    public func importFiles(at urls: [URL]) throws -> IsiXImportResult {
        var result = IsiXImportResult(importedFiles: [], studyInstanceUIDs: [], seriesInstanceUIDs: [], failures: [])
        for written in stubWritten where written.files.contains(where: { urls.contains($0) }) {
            guard written.files.allSatisfy({ FileManager.default.fileExists(atPath: $0.path) }) else {
                result.failures.append(.init(file: written.files[0], reason: "file missing"))
                continue
            }
            let uid = written.request.seriesInstanceUID ?? "9.9.\(stubSeries.count + 1)"
            stubSeries.append(IsiXSeries(stubUID: uid, studyUID: written.request.studyInstanceUID,
                                         description: written.request.seriesDescription, modality: "SC",
                                         imageCount: written.request.images.count))
            result.importedFiles += written.files
            result.seriesInstanceUIDs.append(uid)
            if !result.studyInstanceUIDs.contains(written.request.studyInstanceUID) {
                result.studyInstanceUIDs.append(written.request.studyInstanceUID)
            }
        }
        return result
    }
}

// MARK: - Tarefas

public final class IsiXTaskProgress: @unchecked Sendable {
    private let lock = NSLock()
    private var fraction = 0.0
    private var text: String?
    private var cancelled = false

    private func locked<T>(_ body: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }

    public var fractionCompleted: Double { locked { fraction } }
    public var message: String? { locked { text } }
    public var isCancelled: Bool { locked { cancelled } }

    public func report(_ fraction: Double, message: String? = nil) {
        locked {
            self.fraction = fraction
            if let message { text = message }
        }
    }

    public func stubCancel() { locked { cancelled = true } }

    /// No kit de verdade só o IsiX cria o andamento; os testes usam esta porta.
    public static func stubMake() -> IsiXTaskProgress { IsiXTaskProgress() }
}

@MainActor public final class IsiXTask {
    public let name: String
    public let progress: IsiXTaskProgress
    public private(set) var isFinished = false
    public private(set) var error: (any Error)?
    var stubWork: Task<Void, Never>?

    init(name: String, progress: IsiXTaskProgress) {
        self.name = name
        self.progress = progress
    }

    public func cancel() {
        progress.stubCancel()
        stubWork?.cancel()
    }

    public func value() async throws {
        await stubWork?.value
        if let error { throw error }
    }

    func stubFinish(_ error: (any Error)?) {
        self.error = error
        isFinished = true
    }
}

// MARK: - Plugin e contexto

public struct IsiXPluginInfo: Sendable, Equatable {
    public let identifier: String
    public let name: String
    public let version: String
    public let bundleURL: URL
    public let capabilities: Set<IsiXCapability>

    public init(stubIdentifier: String, name: String, version: String) {
        identifier = stubIdentifier
        self.name = name
        self.version = version
        bundleURL = URL(fileURLWithPath: "/tmp/\(name).isixplugin")
        capabilities = []
    }
}

@MainActor public protocol IsiXPlugin: AnyObject {
    init()
    func activate(with context: IsiXPluginContext) throws
    func deactivate()
}

extension IsiXPlugin {
    public func deactivate() {}
}

@MainActor public final class IsiXPluginContext {
    public typealias StubCommandHandler = @MainActor @Sendable (IsiXCommandInvocation) throws -> Void
    public typealias StubInputHandler = @MainActor @Sendable (IsiXViewerInput) -> Bool

    public let info: IsiXPluginInfo

    public var stubViewers: [IsiXViewer] = []
    public var stubCommands: [(command: IsiXCommand, handler: StubCommandHandler)] = []
    public var stubInputHandlers: [(kinds: IsiXInputKinds, handler: StubInputHandler)] = []
    public let stubDatabase = IsiXDatabase()
    public var stubTasks: [IsiXTask] = []

    public init(stubInfo: IsiXPluginInfo = IsiXPluginInfo(stubIdentifier: "app.neurolaudo.isixplugin", name: "NeuroLaudo", version: "0")) {
        info = stubInfo
        stubDatabase.stubContext = self
    }

    public func register(_ command: IsiXCommand, handler: @escaping @MainActor @Sendable (IsiXCommandInvocation) throws -> Void) throws {
        guard !stubCommands.contains(where: { $0.command.id == command.id }) else {
            throw IsiXPluginError.commandAlreadyRegistered(command.id)
        }
        stubCommands.append((command, handler))
    }

    public func unregisterCommand(id: String) {
        stubCommands.removeAll { $0.command.id == id }
    }

    public func frontmostViewer() throws -> IsiXViewer? { stubViewers.last }

    public func openViewers() throws -> [IsiXViewer] { stubViewers }

    public func viewer(withID id: IsiXViewerID) throws -> IsiXViewer? {
        stubViewers.first { $0.id == id }
    }

    public var stubObservers: [(kinds: IsiXEventKinds, handler: @MainActor @Sendable (IsiXEvent) -> Void)] = []

    public func observe(_ kinds: IsiXEventKinds = .all, _ handler: @escaping @MainActor @Sendable (IsiXEvent) -> Void) throws -> IsiXObservation {
        stubObservers.append((kinds, handler))
        return IsiXObservation()
    }

    /// Só do stub: entrega um evento a quem o observa, como o IsiX faria.
    public func stubEmit(_ event: IsiXEvent, kind: IsiXEventKinds) {
        for observer in stubObservers where observer.kinds.contains(kind) {
            observer.handler(event)
        }
    }

    public func database() throws -> IsiXDatabase { stubDatabase }

    @discardableResult
    public func startTask(named name: String, _ operation: @escaping @Sendable (IsiXTaskProgress) async throws -> Void) throws -> IsiXTask {
        let progress = IsiXTaskProgress()
        let task = IsiXTask(name: name, progress: progress)
        task.stubWork = Task.detached {
            var failure: (any Error)?
            do { try await operation(progress) } catch { failure = error }
            let outcome = failure
            await MainActor.run { task.stubFinish(outcome) }
        }
        stubTasks.append(task)
        return task
    }

    public func interceptInput(_ kinds: IsiXInputKinds = .all,
                               _ handler: @escaping @MainActor @Sendable (IsiXViewerInput) -> Bool) throws -> IsiXObservation {
        stubInputHandlers.append((kinds, handler))
        return IsiXObservation()
    }

    /// Só do stub: executa um comando registrado, como o menu faria.
    public func stubRun(_ id: String, viewer: IsiXViewer? = nil) throws {
        guard let entry = stubCommands.first(where: { $0.command.id == id }) else {
            throw IsiXPluginError.invalidCommand(id)
        }
        try entry.handler(IsiXCommandInvocation(stubCommand: entry.command, viewer: viewer ?? stubViewers.last))
    }
}
