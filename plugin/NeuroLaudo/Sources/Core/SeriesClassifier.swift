//  NeuroLaudo — reconhece o tipo de cada série pelo nome (descrição da série).
//  Os nomes variam por fabricante e por hospital; as regras abaixo cobrem os
//  mais comuns e devem ser ajustadas com os nomes reais do serviço.

import Foundation

enum SequenceKind: String, CaseIterable, Sendable {
    case flair, t2, dwi, adc, swi, t2Star, t1, t1Contrast, mra, perfusion
    case ctBrain, ctBone, cta
    case localizer, other

    var label: String {
        switch self {
        case .flair: return "FLAIR"
        case .t2: return "T2"
        case .dwi: return "difusão"
        case .adc: return "ADC"
        case .swi: return "SWI"
        case .t2Star: return "T2*"
        case .t1: return "T1"
        case .t1Contrast: return "T1 pós-contraste"
        case .mra: return "angio-RM"
        case .perfusion: return "perfusão"
        case .ctBrain: return "TC parênquima"
        case .ctBone: return "TC osso"
        case .cta: return "angio-TC"
        case .localizer: return "localizador"
        case .other: return "outra"
        }
    }
}

struct SeriesInfo: Equatable, Sendable {
    var uid: String
    var description: String
    var modality: String
    var imageCount: Int
    var seriesNumber: Int?
}

enum SeriesClassifier {
    /// Maiúsculas, sem acentos, com separadores trocados por espaço. Mantém `+` e `*`.
    static func normalize(_ text: String) -> String {
        let accents: [Character: Character] = [
            "Á": "A", "À": "A", "Â": "A", "Ã": "A", "Ä": "A", "É": "E", "Ê": "E", "È": "E", "Í": "I", "Ì": "I",
            "Ó": "O", "Ô": "O", "Õ": "O", "Ò": "O", "Ú": "U", "Ü": "U", "Ç": "C",
        ]
        var out = ""
        for ch in text.uppercased() {
            let c = accents[ch] ?? ch
            if c.isLetter || c.isNumber || c == "+" || c == "*" {
                out.append(c)
            } else {
                out.append(" ")
            }
        }
        return out.split(separator: " ").joined(separator: " ")
    }

    static func tokens(_ normalized: String) -> [String] {
        normalized.split(separator: " ").map(String.init)
    }

    private static func hasToken(_ tokens: [String], _ candidates: [String]) -> Bool {
        tokens.contains { candidates.contains($0) }
    }

    private static func contains(_ text: String, _ needles: [String]) -> Bool {
        needles.contains { text.contains($0) }
    }

    /// Marcas de contraste no nome da série.
    static func hasContrastMark(_ normalized: String) -> Bool {
        let t = tokens(normalized)
        if hasToken(t, ["GD", "GAD", "GADO", "GADOLINIO", "GADOLINIUM", "POS", "POST", "CE", "CONTRASTE", "CONTRAST", "WC", "+C", "C+", "+GD", "+CE"]) {
            // "SEM CONTRASTE" e "PRE" negam a marca.
            if hasToken(t, ["SEM", "PRE", "WITHOUT", "WO"]) { return false }
            return true
        }
        return false
    }

    static func classify(description: String, modality: String) -> SequenceKind {
        let text = normalize(description)
        let t = tokens(text)
        let mod = modality.uppercased()

        if hasToken(t, ["LOC", "LOCALIZER", "LOCALIZADOR", "SCOUT", "SURVEY", "TOPOGRAM", "TOPOGRAMA", "AAHEAD", "CALIBRATION", "PLANE"])
            || contains(text, ["3 PLANE", "3PLANE"]) {
            return .localizer
        }

        if mod == "CT" {
            if contains(text, ["ANGIO", "CTA", "ARTERIAL", "VENOSA", "VENOGRAFIA"]) { return .cta }
            if contains(text, ["OSSO", "OSSEA", "BONE"]) { return .ctBone }
            if contains(text, ["DOSE", "PROTOCOL", "SCREEN"]) { return .other }
            return .ctBrain
        }

        guard mod == "MR" else { return .other }

        let isT1 = hasToken(t, ["T1", "T1W", "T1WI", "MPRAGE", "MP2RAGE", "BRAVO", "SPGR", "FSPGR", "TFE", "VIBE", "IRFSPGR"])
            || contains(text, ["MP RAGE"])

        // Mapas e sequências com nome inequívoco primeiro.
        if hasToken(t, ["EADC"]) { return .other }
        if hasToken(t, ["ADC", "DADC"]) || contains(text, ["APPARENT DIFF"]) { return .adc }
        if hasToken(t, ["PERF", "PERFUSAO", "PERFUSION", "PWI", "DSC", "DCE", "ASL", "PCASL", "CBV", "CBF", "MTT", "TTP", "RCBV", "RCBF"]) {
            return .perfusion
        }
        if hasToken(t, ["DWI", "DIFF", "DIFUSAO", "DIFFUSION", "TRACE", "TRACEW", "B1000", "DW"]) || contains(text, ["EP2D DIFF", "EPI DWI"]) {
            return .dwi
        }
        if hasToken(t, ["SWI", "SWAN", "SWIP", "SUSCEPTIBILIDADE", "SUSCEPTIBILITY", "MINIP"]) || contains(text, ["VEN BOLD"]) {
            return .swi
        }
        if contains(text, ["T2*", "T2 STAR", "T2 ESTRELA"]) || hasToken(t, ["HEMO", "MEDIC"])
            || (hasToken(t, ["GRE", "FFE"]) && !isT1) {
            return .t2Star
        }
        if hasToken(t, ["TOF", "MRA", "ARM", "ANGIO", "ANGIORM", "VENOGRAFIA", "MRV"]) { return .mra }

        // "T1 FLAIR" é uma sequência ponderada em T1.
        if hasToken(t, ["FLAIR", "TIRM"]) || contains(text, ["DARK FLUID"]) {
            return isT1 ? (hasContrastMark(text) ? .t1Contrast : .t1) : .flair
        }
        if isT1 { return hasContrastMark(text) ? .t1Contrast : .t1 }
        if hasToken(t, ["T2", "T2W", "T2WI"]) { return .t2 }
        return .other
    }

    static func classify(_ series: SeriesInfo) -> SequenceKind {
        classify(description: series.description, modality: series.modality)
    }

    /// Série adquirida no plano axial, a julgar pelo nome.
    static func looksAxial(_ description: String) -> Bool {
        hasToken(tokens(normalize(description)), ["AX", "AXI", "AXIAL", "TRA", "TRANS", "TRANSVERSAL", "TRANSVERSE"])
    }
}
