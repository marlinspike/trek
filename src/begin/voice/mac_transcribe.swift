// begin-transcribe: hear a WAV file with the Mac's own speech recogniser, on this Mac (no network).
// usage: begin-transcribe <file.wav> [hint ...]     prints what was said; hints are ship and officer names.
// Exit codes: 0 heard, 1 nothing heard, 2 not allowed (System Settings > Privacy > Speech Recognition),
// 3 no recogniser for the language, 64 bad usage.
// Built by Begin the first time the Mac engine is used (see voice/engines.py), with an Info.plist linked in
// so macOS can ask the captain's permission.
import Foundation
import Speech

func fail(_ msg: String, _ code: Int32) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(code)
}

// The recogniser answers on the main run loop, so wait by running it.
func wait(_ done: () -> Bool, _ seconds: Double) -> Bool {
    let end = Date().addingTimeInterval(seconds)
    while !done() && Date() < end {
        RunLoop.main.run(until: Date().addingTimeInterval(0.02))
    }
    return done()
}

let args = CommandLine.arguments
if args.count < 2 { fail("usage: begin-transcribe <file.wav> [hint ...]", 64) }
let url = URL(fileURLWithPath: args[1])
let hints = Array(args.dropFirst(2))
let locale = ProcessInfo.processInfo.environment["BEGIN_SPEECH_LOCALE"] ?? "en-US"

var status: SFSpeechRecognizerAuthorizationStatus? = nil
SFSpeechRecognizer.requestAuthorization { s in status = s }
if !wait({ status != nil }, 60) || status != .authorized {
    fail("Speech recognition is not allowed. System Settings > Privacy & Security > Speech Recognition.", 2)
}
guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: locale)), recognizer.isAvailable else {
    fail("No speech recogniser for \(locale) on this Mac.", 3)
}
let request = SFSpeechURLRecognitionRequest(url: url)
if recognizer.supportsOnDeviceRecognition { request.requiresOnDeviceRecognition = true }
request.contextualStrings = hints
request.shouldReportPartialResults = false
request.taskHint = .search

var text: String? = nil
var finished = false
let task = recognizer.recognitionTask(with: request) { result, error in
    if let r = result, r.isFinal {
        text = r.bestTranscription.formattedString
        finished = true
    } else if error != nil {
        finished = true
    }
}
if !wait({ finished }, 20) { task.cancel() }
guard let heard = text, !heard.isEmpty else { exit(1) }
print(heard)
