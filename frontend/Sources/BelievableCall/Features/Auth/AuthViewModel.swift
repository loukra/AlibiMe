import Foundation
import Observation

/// Drives the pre-auth flow: welcome → phone entry → OTP → done. The verified
/// number rule is reinforced in copy here; the user only ever enters their own
/// number for login.
@MainActor
@Observable
public final class AuthViewModel {
    public enum Step: Equatable {
        case welcome
        case phone
        case otp
        case done
    }

    public private(set) var step: Step = .welcome
    /// The country whose dial code goes in front of `phoneNumber`.
    public var country: PhoneCountry = .default
    /// What the user typed: the national number, or a full one starting with +.
    public var phoneNumber: String = ""
    public var code: String = ""
    public var locale: String = "en"
    public private(set) var isLoading = false
    public private(set) var errorMessage: String?
    public private(set) var verificationID: String?
    public private(set) var session: Session?
    /// Seconds until the user may request a new code. 0 means resend is allowed.
    public private(set) var resendCountdown: Int = 0

    private let auth: AuthServicing
    private let deviceID: String?
    /// Called once a session has been obtained.
    public var onAuthenticated: ((Session) -> Void)?

    public init(auth: AuthServicing, deviceID: String? = nil) {
        self.auth = auth
        self.deviceID = deviceID
    }

    public func begin() { step = .phone }

    /// Returns the flow to its start. Used when the auth screen reappears after
    /// sign-out / session expiry so the user doesn't land on a stale step.
    public func reset() {
        step = .welcome
        phoneNumber = ""
        code = ""
        verificationID = nil
        session = nil
        errorMessage = nil
        resendCountdown = 0
        isLoading = false
    }

    public var canSubmitPhone: Bool {
        !isLoading && fullNumber != nil
    }

    /// A number typed or pasted with + (or 00) picks its country in the menu
    /// and keeps only the rest in the field, so the menu never contradicts it.
    public func phoneNumberChanged() {
        let trimmed = phoneNumber.trimmingCharacters(in: .whitespaces)
        guard trimmed.hasPrefix("+") || trimmed.hasPrefix("00") else { return }
        var digits = trimmed.filter(\.isNumber)
        if trimmed.hasPrefix("00") { digits.removeFirst(2) }
        // Longest dial code first (+352 before +35…); the list order breaks ties (+1 is US).
        let match = PhoneCountry.all
            .filter { digits.hasPrefix($0.dialCode) }
            .max { $0.dialCode.count < $1.dialCode.count }
        guard let match, digits.count > match.dialCode.count + 4 else { return }
        country = match
        phoneNumber = String(digits.dropFirst(match.dialCode.count))
    }

    /// The number in international form, as the code is sent to it.
    public var fullNumber: String? {
        AuthViewModel.normalizedPhone(phoneNumber, dialCode: country.dialCode)
    }

    public var canSubmitCode: Bool {
        !isLoading && code.trimmingCharacters(in: .whitespaces).count >= 4
    }

    /// Strips formatting (spaces, parens, dashes) into a light E.164 candidate.
    /// A number starting with + is taken as is; otherwise a leading 0 (the
    /// trunk prefix, as in 0151…) is dropped and the dial code goes in front.
    /// The backend is authoritative for true validation.
    static func normalizedPhone(_ raw: String, dialCode: String) -> String? {
        let trimmed = raw.trimmingCharacters(in: .whitespaces)
        var digits = trimmed.filter(\.isNumber)
        if trimmed.hasPrefix("+") || trimmed.hasPrefix("00") {
            if trimmed.hasPrefix("00") { digits.removeFirst(2) }
            return digits.count >= 6 ? "+\(digits)" : nil
        }
        while digits.hasPrefix("0") { digits.removeFirst() }
        guard digits.count >= 5 else { return nil }
        return "+\(dialCode)\(digits)"
    }

    public func requestCode() async {
        guard let normalized = fullNumber else {
            errorMessage = "Enter your phone number."
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let result = try await auth.start(phoneNumber: normalized, locale: locale, deviceID: deviceID)
            verificationID = result.verificationID
            step = .otp
            code = ""
            startResendCountdown()
        } catch {
            errorMessage = ErrorCopy.userMessage(for: asAPIError(error))
        }
    }

    public func confirmCode() async {
        guard let verificationID else {
            errorMessage = "Request a code first."
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let session = try await auth.confirm(verificationID: verificationID,
                                                 code: code.trimmingCharacters(in: .whitespaces),
                                                 deviceID: deviceID)
            self.session = session
            step = .done
            onAuthenticated?(session)
        } catch {
            errorMessage = ErrorCopy.userMessage(for: asAPIError(error))
        }
    }

    public func editPhoneNumber() {
        step = .phone
        verificationID = nil
        code = ""
        errorMessage = nil
    }

    public func resend() async {
        guard resendCountdown == 0 else { return }
        await requestCode()
    }

    /// Advances the resend countdown by one second; the view drives this with a
    /// timer. Kept here so behavior is unit-testable without real time.
    public func tick() {
        if resendCountdown > 0 { resendCountdown -= 1 }
    }

    private func startResendCountdown() { resendCountdown = 30 }
}

/// A country in the login's dial-code menu. Germany comes first and is the
/// default; a number typed with + overrides the menu.
public struct PhoneCountry: Identifiable, Hashable, Sendable {
    public let regionCode: String
    public let name: String
    public let dialCode: String
    public var id: String { regionCode }

    /// The region's flag, built from its two letters.
    public var flag: String {
        regionCode.unicodeScalars
            .compactMap { UnicodeScalar(127397 + $0.value) }
            .map(String.init)
            .joined()
    }

    public static let `default` = PhoneCountry(regionCode: "DE", name: "Germany", dialCode: "49")

    public static let all: [PhoneCountry] = [
        .default,
        PhoneCountry(regionCode: "AT", name: "Austria", dialCode: "43"),
        PhoneCountry(regionCode: "CH", name: "Switzerland", dialCode: "41"),
        PhoneCountry(regionCode: "NL", name: "Netherlands", dialCode: "31"),
        PhoneCountry(regionCode: "BE", name: "Belgium", dialCode: "32"),
        PhoneCountry(regionCode: "LU", name: "Luxembourg", dialCode: "352"),
        PhoneCountry(regionCode: "FR", name: "France", dialCode: "33"),
        PhoneCountry(regionCode: "DK", name: "Denmark", dialCode: "45"),
        PhoneCountry(regionCode: "PL", name: "Poland", dialCode: "48"),
        PhoneCountry(regionCode: "CZ", name: "Czechia", dialCode: "420"),
        PhoneCountry(regionCode: "IT", name: "Italy", dialCode: "39"),
        PhoneCountry(regionCode: "ES", name: "Spain", dialCode: "34"),
        PhoneCountry(regionCode: "GB", name: "United Kingdom", dialCode: "44"),
        PhoneCountry(regionCode: "IE", name: "Ireland", dialCode: "353"),
        PhoneCountry(regionCode: "SE", name: "Sweden", dialCode: "46"),
        PhoneCountry(regionCode: "NO", name: "Norway", dialCode: "47"),
        PhoneCountry(regionCode: "US", name: "United States", dialCode: "1"),
        PhoneCountry(regionCode: "CA", name: "Canada", dialCode: "1"),
    ]
}
