// mic_control: microphone state and mute through CoreAudio, for mic.sh.
//
//   mic_control status   prints the default input device as key=value lines:
//                          device=<name>
//                          volume=<0-100, or empty when the device has none>
//                          muted=<1 when its mute switch is on, else 0>
//                          canmute=<1 when its mute switch can be set, else 0>
//   mic_control mute     turns the mute switch on for every input device that has
//   mic_control unmute   one (so a device plugged in later is in the same state);
//                        exits 2 when no input device has one
//
// mic.sh compiles this once into its cache folder (it never ships a binary):
//   swiftc -O mic_control.swift -o "${TMPDIR:-/tmp}/wingbar-mic/mic_control"
// It reads and sets audio device properties only: no recording, no network.

import CoreAudio
import Foundation

let system = AudioObjectID(kAudioObjectSystemObject)
let inputScope = kAudioDevicePropertyScopeInput

func address(_ selector: AudioObjectPropertySelector,
             _ scope: AudioObjectPropertyScope = kAudioObjectPropertyScopeGlobal,
             _ element: AudioObjectPropertyElement = kAudioObjectPropertyElementMain) -> AudioObjectPropertyAddress {
    AudioObjectPropertyAddress(mSelector: selector, mScope: scope, mElement: element)
}

func allDevices() -> [AudioDeviceID] {
    var addr = address(kAudioHardwarePropertyDevices)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(system, &addr, 0, nil, &size) == noErr, size > 0 else { return [] }
    var ids = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.stride)
    guard AudioObjectGetPropertyData(system, &addr, 0, nil, &size, &ids) == noErr else { return [] }
    return ids
}

func defaultInput() -> AudioDeviceID? {
    var addr = address(kAudioHardwarePropertyDefaultInputDevice)
    var id = AudioDeviceID(0)
    var size = UInt32(MemoryLayout<AudioDeviceID>.size)
    guard AudioObjectGetPropertyData(system, &addr, 0, nil, &size, &id) == noErr, id != 0 else { return nil }
    return id
}

func hasInput(_ id: AudioDeviceID) -> Bool {
    var addr = address(kAudioDevicePropertyStreamConfiguration, inputScope)
    var size: UInt32 = 0
    guard AudioObjectGetPropertyDataSize(id, &addr, 0, nil, &size) == noErr, size > 0 else { return false }
    let raw = UnsafeMutableRawPointer.allocate(byteCount: Int(size), alignment: MemoryLayout<AudioBufferList>.alignment)
    defer { raw.deallocate() }
    guard AudioObjectGetPropertyData(id, &addr, 0, nil, &size, raw) == noErr else { return false }
    let list = UnsafeMutableAudioBufferListPointer(raw.assumingMemoryBound(to: AudioBufferList.self))
    return list.contains { $0.mNumberChannels > 0 }
}

func name(_ id: AudioDeviceID) -> String {
    var addr = address(kAudioObjectPropertyName)
    var value: Unmanaged<CFString>?
    var size = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
    guard AudioObjectGetPropertyData(id, &addr, 0, nil, &size, &value) == noErr, let s = value else { return "" }
    return s.takeRetainedValue() as String
}

/// The elements a property lives on: the main element, else channels 1 and 2.
func elements(_ id: AudioDeviceID, _ selector: AudioObjectPropertySelector) -> [AudioObjectPropertyElement] {
    [kAudioObjectPropertyElementMain, 1, 2].filter { el in
        var addr = address(selector, inputScope, el)
        return AudioObjectHasProperty(id, &addr)
    }
}

func settable(_ id: AudioDeviceID, _ selector: AudioObjectPropertySelector, _ el: AudioObjectPropertyElement) -> Bool {
    var addr = address(selector, inputScope, el)
    var ok: DarwinBoolean = false
    return AudioObjectIsPropertySettable(id, &addr, &ok) == noErr && ok.boolValue
}

func volume(_ id: AudioDeviceID) -> Int? {
    let els = elements(id, kAudioDevicePropertyVolumeScalar)
    guard !els.isEmpty else { return nil }
    var total: Float32 = 0
    var count = 0
    for el in els {
        var addr = address(kAudioDevicePropertyVolumeScalar, inputScope, el)
        var v: Float32 = 0
        var size = UInt32(MemoryLayout<Float32>.size)
        if AudioObjectGetPropertyData(id, &addr, 0, nil, &size, &v) == noErr {
            total += v
            count += 1
        }
        if el == kAudioObjectPropertyElementMain && count > 0 { break }
    }
    return count > 0 ? Int((total / Float32(count) * 100).rounded()) : nil
}

func muted(_ id: AudioDeviceID) -> Bool {
    for el in elements(id, kAudioDevicePropertyMute) {
        var addr = address(kAudioDevicePropertyMute, inputScope, el)
        var v: UInt32 = 0
        var size = UInt32(MemoryLayout<UInt32>.size)
        if AudioObjectGetPropertyData(id, &addr, 0, nil, &size, &v) == noErr { return v != 0 }
    }
    return false
}

func canMute(_ id: AudioDeviceID) -> Bool {
    elements(id, kAudioDevicePropertyMute).contains { settable(id, kAudioDevicePropertyMute, $0) }
}

@discardableResult
func setMute(_ id: AudioDeviceID, _ on: Bool) -> Bool {
    var done = false
    for el in elements(id, kAudioDevicePropertyMute) where settable(id, kAudioDevicePropertyMute, el) {
        var addr = address(kAudioDevicePropertyMute, inputScope, el)
        var v: UInt32 = on ? 1 : 0
        if AudioObjectSetPropertyData(id, &addr, 0, nil, UInt32(MemoryLayout<UInt32>.size), &v) == noErr {
            done = true
        }
    }
    return done
}

/// One line of output: no line breaks in values.
func clean(_ s: String) -> String {
    String(s.unicodeScalars.filter { !CharacterSet.controlCharacters.contains($0) })
}

let command = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "status"
switch command {
case "mute", "unmute":
    let changed = allDevices().filter(hasInput).map { setMute($0, command == "mute") }
    exit(changed.contains(true) ? 0 : 2)
case "status":
    guard let id = defaultInput() else {
        print("device=")
        exit(0)
    }
    print("device=\(clean(name(id)))")
    print("volume=\(volume(id).map(String.init) ?? "")")
    print("muted=\(muted(id) ? 1 : 0)")
    print("canmute=\(canMute(id) ? 1 : 0)")
default:
    FileHandle.standardError.write("usage: mic_control status|mute|unmute\n".data(using: .utf8)!)
    exit(64)
}
