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
    /// The account language (calls, texts, alibi wording); a new account
    /// starts in the language the app is shown in.
    public var locale: String = AppLanguage.current
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

    /// The same number for reading: "+49 1701234599", not "+491701234599".
    /// A no-break space keeps the dial code on the number's line.
    public var displayNumber: String {
        guard let full = fullNumber else { return phoneNumber }
        let prefix = "+\(country.dialCode)"
        guard full.hasPrefix(prefix) else { return full }
        return "\(prefix)\u{00A0}\(full.dropFirst(prefix.count))"
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
            errorMessage = String(localized: "Enter your phone number.")
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
            errorMessage = String(localized: "Request a code first.")
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
    public let dialCode: String
    /// The country's name in the language iOS shows the app in.
    public var name: String { Locale.current.localizedString(forRegionCode: regionCode) ?? regionCode }
    public var id: String { regionCode }

    /// The region's flag, built from its two letters.
    public var flag: String {
        regionCode.unicodeScalars
            .compactMap { UnicodeScalar(127397 + $0.value) }
            .map(String.init)
            .joined()
    }

    public static let `default` = PhoneCountry(regionCode: "DE", dialCode: "49")

    public static let all: [PhoneCountry] = [
        .default,
        PhoneCountry(regionCode: "AT", dialCode: "43"),
        PhoneCountry(regionCode: "CH", dialCode: "41"),
        PhoneCountry(regionCode: "NL", dialCode: "31"),
        PhoneCountry(regionCode: "BE", dialCode: "32"),
        PhoneCountry(regionCode: "LU", dialCode: "352"),
        PhoneCountry(regionCode: "FR", dialCode: "33"),
        PhoneCountry(regionCode: "DK", dialCode: "45"),
        PhoneCountry(regionCode: "PL", dialCode: "48"),
        PhoneCountry(regionCode: "CZ", dialCode: "420"),
        PhoneCountry(regionCode: "IT", dialCode: "39"),
        PhoneCountry(regionCode: "ES", dialCode: "34"),
        PhoneCountry(regionCode: "GB", dialCode: "44"),
        PhoneCountry(regionCode: "IE", dialCode: "353"),
        PhoneCountry(regionCode: "SE", dialCode: "46"),
        PhoneCountry(regionCode: "NO", dialCode: "47"),
        PhoneCountry(regionCode: "US", dialCode: "1"),
        PhoneCountry(regionCode: "CA", dialCode: "1"),
    ]
}
