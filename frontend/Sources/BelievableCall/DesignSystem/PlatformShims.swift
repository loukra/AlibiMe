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

    /// Hides the default opaque background of scrollable containers (List/Form)
    /// so a custom backdrop can show through.
    @ViewBuilder func bcClearScrollBackground() -> some View {
        if #available(iOS 16, macOS 13, *) {
            self.scrollContentBackground(.hidden)
        } else {
            self
        }
    }

    /// Constrains a vertical ScrollView to vertical motion only: horizontal
    /// rubber-banding is suppressed unless content is genuinely wider than the
    /// viewport, which stops the sideways "jiggle" from sub-pixel overflow.
    @ViewBuilder func bcVerticalScrollOnly() -> some View {
        if #available(iOS 16.4, macOS 13.3, *) {
            self.scrollBounceBehavior(.basedOnSize, axes: .horizontal)
        } else {
            self
        }
    }

    /// Pins scroll content to exactly the container's width so no child can make
    /// the content wider than the viewport (which is what enables a stray
    /// horizontal scroll inside a vertical ScrollView). Apply to the content
    /// *after* its padding.
    @ViewBuilder func bcPinScrollWidth() -> some View {
        if #available(iOS 17, macOS 14, *) {
            self.containerRelativeFrame(.horizontal)
        } else {
            self.frame(maxWidth: .infinity)
        }
    }

    /// Native bottom-sheet presentation: medium/large detents plus a drag handle.
    @ViewBuilder func bcSheetDetents() -> some View {
        if #available(iOS 16, macOS 13, *) {
            self.presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        } else {
            self
        }
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
