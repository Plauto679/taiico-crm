// Local-only OCR. No network, file writes, or document-controlled commands.
import Foundation
import Vision
import PDFKit
import AppKit
import ImageIO

struct Line: Codable { let text: String; let confidence: Float }
struct Page: Codable { let page: Int; let text: String; let method: String; let lines: [Line] }
struct Output: Codable { let pages: [Page] }
enum Failure: Error { case invalidInput }
func recognize(_ image: CGImage, page: Int) throws -> Page {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["es-ES", "en-US"]
    request.usesLanguageCorrection = false // Preserve identifiers; never "correct" RFC/CURP.
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    let lines = (request.results ?? []).compactMap { observation -> Line? in
        guard let value = observation.topCandidates(1).first else { return nil }
        return Line(text: value.string, confidence: value.confidence)
    }
    return Page(page: page, text: lines.map { $0.text }.joined(separator: "\n"), method: "ocr", lines: lines)
}
do {
    guard CommandLine.arguments.count == 2 else { throw Failure.invalidInput }
    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    let data = try Data(contentsOf: url)
    guard data.count <= 4 * 1024 * 1024 else { throw Failure.invalidInput }
    var pages: [Page] = []
    if data.starts(with: Data("%PDF-".utf8)) {
        guard let pdf = PDFDocument(data: data), !pdf.isLocked, pdf.pageCount <= 30 else { throw Failure.invalidInput }
        for index in 0..<pdf.pageCount {
            try autoreleasepool {
                guard let page = pdf.page(at: index) else { throw Failure.invalidInput }
                let bounds = page.bounds(for: .mediaBox)
                guard bounds.width > 0, bounds.height > 0 else { throw Failure.invalidInput }
                let scale = min(2.5, 2200 / max(bounds.width, bounds.height))
                let size = NSSize(width: bounds.width * scale, height: bounds.height * scale)
                let thumbnail = page.thumbnail(of: size, for: .mediaBox)
                guard let cg = thumbnail.cgImage(forProposedRect: nil, context: nil, hints: nil) else { throw Failure.invalidInput }
                pages.append(try recognize(cg, page: index + 1))
            }
        }
    } else {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let cg = CGImageSourceCreateThumbnailAtIndex(source, 0, [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceThumbnailMaxPixelSize: 2400, kCGImageSourceCreateThumbnailWithTransform: true] as CFDictionary)
        else { throw Failure.invalidInput }
        pages.append(try recognize(cg, page: 1))
    }
    let result = try JSONEncoder().encode(Output(pages: pages))
    guard result.count <= 1500000 else { throw Failure.invalidInput }
    FileHandle.standardOutput.write(result)
} catch {
    // Do not log document text or filesystem paths.
    FileHandle.standardError.write(Data("OCR could not read the supplied document.\n".utf8))
    exit(1)
}
