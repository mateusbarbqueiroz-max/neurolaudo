import XCTest
@testable import NeuroLaudo

final class SeriesClassifierTests: XCTestCase {
    private func kind(_ description: String, _ modality: String = "MR") -> SequenceKind {
        SeriesClassifier.classify(description: description, modality: modality)
    }

    func testNormalize() {
        XCTAssertEqual(SeriesClassifier.normalize("t1_mprage_sag-p2 iso +C"), "T1 MPRAGE SAG P2 ISO +C")
        XCTAssertEqual(SeriesClassifier.normalize("AXIAL T1 PÓS-CONTRASTE"), "AXIAL T1 POS CONTRASTE")
    }

    func testSiemensNames() {
        XCTAssertEqual(kind("t2_tirm_tra_dark-fluid"), .flair)
        XCTAssertEqual(kind("ep2d_diff_3scan_trace_p2"), .dwi)
        XCTAssertEqual(kind("ep2d_diff_3scan_trace_p2_ADC"), .adc)
        XCTAssertEqual(kind("t2_swi_tra_p2_1.5mm"), .swi)
        XCTAssertEqual(kind("t1_mprage_sag_p2_iso"), .t1)
        XCTAssertEqual(kind("t1_mprage_sag_p2_iso +C"), .t1Contrast)
        XCTAssertEqual(kind("t1_se_tra_GD"), .t1Contrast)
        XCTAssertEqual(kind("t2_tse_tra"), .t2)
        XCTAssertEqual(kind("TOF_3D_multi-slab"), .mra)
        XCTAssertEqual(kind("localizer"), .localizer)
    }

    func testGENames() {
        XCTAssertEqual(kind("Ax T2 FLAIR"), .flair)
        XCTAssertEqual(kind("Ax DWI b1000"), .dwi)
        XCTAssertEqual(kind("ADC (10^-6 mm²/s)"), .adc)
        XCTAssertEqual(kind("eADC"), .other)
        XCTAssertEqual(kind("Ax SWAN"), .swi)
        XCTAssertEqual(kind("Sag T1 FLAIR"), .t1)
        XCTAssertEqual(kind("Ax 3D BRAVO +C"), .t1Contrast)
        XCTAssertEqual(kind("Ax GRE"), .t2Star)
        XCTAssertEqual(kind("3-Plane Loc"), .localizer)
    }

    func testPhilipsNames() {
        XCTAssertEqual(kind("FLAIR AX"), .flair)
        XCTAssertEqual(kind("DWI SENSE"), .dwi)
        XCTAssertEqual(kind("dADC"), .adc)
        XCTAssertEqual(kind("SWIp"), .swi)
        XCTAssertEqual(kind("VEN_BOLD"), .swi)
        XCTAssertEqual(kind("T1W_3D_TFE"), .t1)
        XCTAssertEqual(kind("T1W_3D_TFE GADO"), .t1Contrast)
        XCTAssertEqual(kind("T2W_FFE"), .t2Star)
        XCTAssertEqual(kind("T1W_3D_FFE"), .t1)
        XCTAssertEqual(kind("T2W_TSE"), .t2)
    }

    func testPortugueseNames() {
        XCTAssertEqual(kind("AXIAL T1 PÓS CONTRASTE"), .t1Contrast)
        XCTAssertEqual(kind("AXIAL T1 SEM CONTRASTE"), .t1)
        XCTAssertEqual(kind("AXIAL DIFUSÃO"), .dwi)
        XCTAssertEqual(kind("PERFUSÃO T2*"), .perfusion)
        XCTAssertEqual(kind("ANGIO RM ARTERIAL"), .mra)
    }

    func testCTNames() {
        XCTAssertEqual(kind("CRANIO SEM CONTRASTE", "CT"), .ctBrain)
        XCTAssertEqual(kind("CRANIO JANELA OSSEA", "CT"), .ctBone)
        XCTAssertEqual(kind("Head 1.0 Bone", "CT"), .ctBone)
        XCTAssertEqual(kind("ANGIO TC ARTERIAL", "CT"), .cta)
        XCTAssertEqual(kind("Topograma", "CT"), .localizer)
        XCTAssertEqual(kind("Dose Report", "CT"), .other)
    }

    func testOtherModalitiesAreNotGuessed() {
        XCTAssertEqual(kind("T1 qualquer", "SR"), .other)
    }

    func testAxialDetection() {
        XCTAssertTrue(SeriesClassifier.looksAxial("t2_tirm_tra_dark-fluid"))
        XCTAssertTrue(SeriesClassifier.looksAxial("Ax T2 FLAIR"))
        XCTAssertFalse(SeriesClassifier.looksAxial("t1_mprage_sag_p2_iso"))
    }
}

final class ProtocolTests: XCTestCase {
    private func s(_ uid: String, _ description: String, _ modality: String = "MR", images: Int = 30, number: Int? = nil) -> SeriesInfo {
        SeriesInfo(uid: uid, description: description, modality: modality, imageCount: images, seriesNumber: number)
    }

    func testMRBrainOrderAndMissing() {
        let series = [
            s("loc", "localizer", images: 3),
            s("t1", "t1_mprage_sag_p2_iso", images: 176),
            s("dwi", "ep2d_diff_3scan_trace_p2"),
            s("adc", "ep2d_diff_3scan_trace_p2_ADC"),
            s("flair", "t2_tirm_tra_dark-fluid"),
            s("t2", "t2_tse_tra"),
            s("t1gd", "t1_mprage_sag_p2_iso +C", images: 176),
        ]
        let selection = NeuroProtocols.select(NeuroProtocols.mrBrain, from: series)
        XCTAssertEqual(selection.series.map(\.uid), ["flair", "dwi", "adc", "t1", "t1gd"])
        XCTAssertEqual(selection.missing, ["SWI ou T2*"])
    }

    func testPrefersAxialThenMoreImages() {
        let series = [
            s("flair-sag", "SAG FLAIR 3D", images: 180),
            s("flair-ax", "AX FLAIR", images: 28),
            s("t2star", "AX GRE"),
            s("swi", "AX SWAN", images: 60),
        ]
        let selection = NeuroProtocols.select(NeuroProtocols.mrBrain, from: series)
        XCTAssertEqual(selection.series.first?.uid, "flair-ax")
        // SWI tem preferência sobre T2* na mesma posição.
        XCTAssertTrue(selection.series.map(\.uid).contains("swi"))
        XCTAssertFalse(selection.series.map(\.uid).contains("t2star"))
    }

    func testCTHead() {
        let series = [
            s("osso", "CRANIO JANELA OSSEA", "CT", images: 200),
            s("topo", "Topograma", "CT", images: 2),
            s("par", "CRANIO SEM CONTRASTE", "CT", images: 200),
        ]
        let selection = NeuroProtocols.select(NeuroProtocols.ctHead, from: series)
        XCTAssertEqual(selection.series.map(\.uid), ["par", "osso"])
        XCTAssertEqual(selection.missing, ["angio-TC"])
    }

    func testProtocolForModalities() {
        XCTAssertEqual(NeuroProtocols.protocolFor(modalities: ["SR", "mr"])?.id, NeuroProtocols.mrBrain.id)
        XCTAssertEqual(NeuroProtocols.protocolFor(modalities: ["CT"])?.id, NeuroProtocols.ctHead.id)
        XCTAssertNil(NeuroProtocols.protocolFor(modalities: ["US"]))
    }

    func testPreviousStudy() {
        func study(_ uid: String, _ day: Double, _ modalities: [String]) -> StudyInfo {
            StudyInfo(uid: uid, date: Date(timeIntervalSince1970: day * 86_400), modalities: modalities, description: nil)
        }
        let current = study("now", 100, ["MR"])
        let all = [current, study("ct-recent", 90, ["CT"]), study("mr-old", 10, ["MR"]), study("mr-prev", 60, ["MR", "SR"]),
                   study("mr-future", 120, ["MR"])]
        XCTAssertEqual(PriorStudies.previous(of: current, among: all)?.uid, "mr-prev")
        XCTAssertNil(PriorStudies.previous(of: study("first", 1, ["MR"]), among: all))
    }

    func testCounterpartSeries() {
        let current = s("cur", "AX FLAIR")
        let prior = [s("p-sag", "SAG FLAIR 3D", images: 180), s("p-ax", "Ax T2 FLAIR"), s("p-t1", "AX T1")]
        XCTAssertEqual(PriorStudies.counterpart(of: current, in: prior)?.uid, "p-ax")
        // Mesmo nome ganha de tudo.
        XCTAssertEqual(PriorStudies.counterpart(of: current, in: prior + [s("p-same", "ax flair", images: 5)])?.uid, "p-same")
        XCTAssertNil(PriorStudies.counterpart(of: s("x", "série desconhecida"), in: prior))
    }
}
