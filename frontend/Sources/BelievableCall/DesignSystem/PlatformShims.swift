#if canImport(SwiftUI)
import SwiftUI

// Small shims so the UI compiles on both iOS (the shipping target) and macOS
// (the host used for `swift test`). iOS-only modifiers are applied only on iOS;
// on macOS they no-op.
extension View {
    /// Applies an inline navigation title on iOS.
    @ViewBuilder func bcInlineNavTitle() -> some View {
        #if os(iOS)
        self.navigationBarTitleDisplayMode(.inline)
        #else
        self
        #endif
    }

    /// Phone-pad keyboard for number entry on iOS.
    @ViewBuilder func bcPhoneKeyboard() -> some View {
        #if os(iOS)
        self.keyboardType(.phonePad).textContentType(.telephoneNumber)
        #else
        self
        #endif
    }

    /// Numeric (OTP) keyboard on iOS.
    @ViewBuilder func bcNumberKeyboard() -> some View {
        #if os(iOS)
        self.keyboardType(.numberPad).textContentType(.oneTimeCode)
        #else
        self
        #endif
    }
}

/// Light haptic feedback on primary/success/cancel actions. No-ops where the
/// generator isn't available.
public enum Haptics {
    public enum Kind { case impact, success, warning }

    public static func play(_ kind: Kind) {
        #if os(iOS)
        switch kind {
        case .impact:
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        case .success:
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        case .warning:
            UINotificationFeedbackGenerator().notificationOccurred(.warning)
        }
        #endif
    }
}
#endif
