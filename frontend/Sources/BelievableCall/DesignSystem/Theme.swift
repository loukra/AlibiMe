#if canImport(SwiftUI)
import SwiftUI

#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

/// Minimal, premium, discreet design tokens. One calm accent, one success, one
/// warning, one destructive; light and dark from day one. The surfaces lean into
/// a soft, cool blue-gray gradient with translucent "glass" cards.
public enum Theme {
    // Brand palette (AlibiMe corporate design):
    //   #121B28 ink navy · #6366F1 indigo · #ADAAFC lavender ·
    //   #F4F5F7 / #F1F2FE / #E2E3FE / #C9CBFB light lavender shades.
    // Accent is the brand indigo (#6366F1); dark mode lightens it (#818CF8) so it
    // stays legible on dark surfaces while keeping white text readable on buttons.
    public static let accent = dynamic(light: (0.388, 0.400, 0.945), dark: (0.506, 0.549, 0.973))
    public static let success = dynamic(light: (0.13, 0.55, 0.33), dark: (0.30, 0.78, 0.50))
    public static let warning = dynamic(light: (0.80, 0.55, 0.05), dark: (0.98, 0.74, 0.25))
    public static let destructive = dynamic(light: (0.80, 0.18, 0.16), dark: (1.0, 0.42, 0.38))

    // Flat surfaces (launch screen, fallbacks). Cards use a translucent material
    // on top of `backgroundGradient`, see `Card`. Light: #F4F5F7; dark: #121B28.
    public static let background = dynamic(light: (0.957, 0.961, 0.969), dark: (0.071, 0.106, 0.157))
    public static let card = dynamic(light: (1.0, 1.0, 1.0), dark: (0.106, 0.145, 0.212))
    public static let subtleBorder = dynamic(light: (0.886, 0.890, 0.996), dark: (0.16, 0.20, 0.28))

    // Soft brand-lavender gradient backdrop (near-white #F4F5F7 settling into the
    // #C9CBFB lavender shade); dark mode is the ink-navy #121B28 deepening below.
    public static let backgroundTop = dynamic(light: (0.957, 0.961, 0.969), dark: (0.094, 0.129, 0.188))
    public static let backgroundBottom = dynamic(light: (0.788, 0.796, 0.984), dark: (0.043, 0.063, 0.094))
    public static var backgroundGradient: LinearGradient {
        LinearGradient(colors: [backgroundTop, backgroundBottom],
                       startPoint: .top, endPoint: .bottom)
    }

    // Glass accents: a bright edge highlight and a soft, diffuse drop shadow.
    public static let glassBorder = dynamic(light: (1, 1, 1, 0.60), dark: (1, 1, 1, 0.12))
    public static let cardShadow = dynamic(light: (0.071, 0.106, 0.157, 0.14), dark: (0, 0, 0, 0.45))

    static func dynamic(light: (Double, Double, Double), dark: (Double, Double, Double)) -> Color {
        dynamic(light: (light.0, light.1, light.2, 1), dark: (dark.0, dark.1, dark.2, 1))
    }

    static func dynamic(
        light: (Double, Double, Double, Double),
        dark: (Double, Double, Double, Double)
    ) -> Color {
        #if canImport(UIKit)
        return Color(UIColor { traits in
            let c = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: c.0, green: c.1, blue: c.2, alpha: c.3)
        })
        #else
        // macOS host (test/preview only): the light variant is sufficient since
        // these views are not rendered as a shipping mac app.
        return Color(red: light.0, green: light.1, blue: light.2).opacity(light.3)
        #endif
    }
}

/// 8-point spacing rhythm.
public enum Spacing {
    public static let xs: CGFloat = 4
    public static let s: CGFloat = 8
    public static let m: CGFloat = 16
    public static let l: CGFloat = 24
    public static let xl: CGFloat = 32
}

public enum Radius {
    public static let card: CGFloat = 22
    public static let control: CGFloat = 14
    public static let pill: CGFloat = 999
}

public extension View {
    /// The standard screen backdrop: the soft gradient, extended under the safe
    /// areas so content (and the floating tab bar) float above a continuous wash.
    func bcScreenBackground() -> some View {
        background(Theme.backgroundGradient.ignoresSafeArea())
    }
}
#endif
