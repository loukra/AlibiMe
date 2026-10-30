import Foundation
#if canImport(DeviceCheck)
import DeviceCheck
#endif

/// A DeviceCheck token for this iPhone. The backend asks Apple with it whether
/// the device already had its free credits, so a new phone number on the same
/// iPhone doesn't get them again (Apple's bit survives reinstalls).
public protocol DeviceTokenProviding: Sendable {
    /// nil where DeviceCheck isn't available (the simulator).
    func deviceToken() async -> String?
}

public struct AppleDeviceToken: DeviceTokenProviding {
    public init() {}

    public func deviceToken() async -> String? {
        #if canImport(DeviceCheck)
        guard DCDevice.current.isSupported else { return nil }
        return try? await DCDevice.current.generateToken().base64EncodedString()
        #else
        return nil
        #endif
    }
}

public struct NoDeviceToken: DeviceTokenProviding {
    public init() {}
    public func deviceToken() async -> String? { nil }
}
