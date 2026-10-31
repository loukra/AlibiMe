// swift-tools-version: 5.10
import PackageDescription

// BelievableCall — iOS frontend.
//
// The app source lives in the `BelievableCall` library. It is built for iOS as
// part of the app, and the same library compiles for macOS so the logic,
// networking, mapping, and view-model layers can be exercised with `swift test`
// on the host. UIKit-only APIs are isolated behind small platform shims so the
// whole package compiles cross-platform.
let package = Package(
    name: "BelievableCall",
    // Lets Xcode extract the package's texts for the app's string catalog
    // (App/BelievableCall/Localizable.xcstrings, see scripts/strings.sh).
    defaultLocalization: "en",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(name: "BelievableCall", targets: ["BelievableCall"]),
    ],
    targets: [
        .target(
            name: "BelievableCall",
            path: "Sources/BelievableCall",
            resources: [.process("Resources")]
        ),
        // Pure unit tests: view-model transitions, mapping, filtering, timing,
        // error copy, session restore. No network required.
        .testTarget(
            name: "BelievableCallTests",
            dependencies: ["BelievableCall"],
            path: "Tests/BelievableCallTests"
        ),
        // Integration tests against the real backend. They are skipped unless
        // BC_BACKEND_URL points at a running server (see README).
        .testTarget(
            name: "BelievableCallIntegrationTests",
            dependencies: ["BelievableCall"],
            path: "Tests/BelievableCallIntegrationTests"
        ),
    ]
)
