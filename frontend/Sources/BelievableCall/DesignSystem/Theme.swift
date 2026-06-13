#if canImport(SwiftUI)
import SwiftUI

#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

/// Minimal, premium, discreet design tokens. One calm accent, one success, one
/// warning, one destructive; light and dark from day one.
public enum Theme {
    // Accent: a calm, confident deep blue.
    public static let accent = dynamic(light: (0.10, 0.32, 0.78), dark: (0.40, 0.60, 1.0))
    public static let success = dynamic(light: (0.13, 0.55, 0.33), dark: (0.30, 0.78, 0.50))
    public static let warning = dynamic(light: (0.80, 0.55, 0.05), dark: (0.98, 0.74, 0.25))
    public static let destructive = dynamic(light: (0.80, 0.18, 0.16), dark: (1.0, 0.42, 0.38))

    // Surfaces: warm white / soft gray in light, charcoal / graphite in dark.
    public static let background = dynamic(light: (0.96, 0.96, 0.97), dark: (0.07, 0.07, 0.08))
    public static let card = dynamic(light: (1.0, 1.0, 1.0), dark: (0.13, 0.13, 0.15))
    public static let subtleBorder = dynamic(light: (0.88, 0.88, 0.90), dark: (0.24, 0.24, 0.27))

    static func dynamic(light: (Double, Double, Double), dark: (Double, Double, Double)) -> Color {
        #if canImport(UIKit)
        return Color(UIColor { traits in
            let c = traits.userInterfaceStyle == .dark ? dark : light
            return UIColor(red: c.0, green: c.1, blue: c.2, alpha: 1)
        })
        #else
        // macOS host (test/preview only): the light variant is sufficient since
        // these views are not rendered as a shipping mac app.
        return Color(red: light.0, green: light.1, blue: light.2)
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
    public static let card: CGFloat = 16
    public static let control: CGFloat = 12
    public static let pill: CGFloat = 999
}
#endif
