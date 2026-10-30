import XCTest
@testable import BelievableCall

@MainActor
final class AuthViewModelTests: XCTestCase {
    func testStartsOnWelcomeThenAdvances() {
        let vm = AuthViewModel(auth: MockAuthService())
        XCTAssertEqual(vm.step, .welcome)
        vm.begin()
        XCTAssertEqual(vm.step, .phone)
    }

    func testPhoneValidationGate() {
        let vm = AuthViewModel(auth: MockAuthService())
        vm.phoneNumber = "abc"
        XCTAssertFalse(vm.canSubmitPhone)
        vm.phoneNumber = "+1 415 555 0123"
        XCTAssertTrue(vm.canSubmitPhone)
    }

    func testGermanyIsTheDefaultCountry() {
        let vm = AuthViewModel(auth: MockAuthService())
        XCTAssertEqual(vm.country.dialCode, "49")
        XCTAssertEqual(vm.country.flag, "🇩🇪")
        vm.phoneNumber = "0151 23456789"
        XCTAssertEqual(vm.fullNumber, "+4915123456789")
        vm.country = PhoneCountry.all.first { $0.regionCode == "AT" }!
        XCTAssertEqual(vm.fullNumber, "+4315123456789")
    }

    func testAPastedInternationalNumberPicksItsCountry() {
        let vm = AuthViewModel(auth: MockAuthService())
        vm.phoneNumber = "+44 7700 900123"
        vm.phoneNumberChanged()
        XCTAssertEqual(vm.country.regionCode, "GB")
        XCTAssertEqual(vm.phoneNumber, "7700900123")
        XCTAssertEqual(vm.fullNumber, "+447700900123")

        vm.phoneNumber = "00352 621 123 456"
        vm.phoneNumberChanged()
        XCTAssertEqual(vm.country.regionCode, "LU", "the longer +352 wins over shorter codes")

        vm.phoneNumber = "+1 415 555 0123"
        vm.phoneNumberChanged()
        XCTAssertEqual(vm.country.regionCode, "US")
    }

    func testAPlusAloneLeavesTheMenuAlone() {
        let vm = AuthViewModel(auth: MockAuthService())
        vm.phoneNumber = "+4"
        vm.phoneNumberChanged()
        XCTAssertEqual(vm.country.regionCode, "DE")
        XCTAssertEqual(vm.phoneNumber, "+4")
    }

    func testNormalizationStripsFormatting() {
        XCTAssertEqual(AuthViewModel.normalizedPhone("+1 (415) 555-0123", dialCode: "49"), "+14155550123")
        XCTAssertEqual(AuthViewModel.normalizedPhone("0151 2345 6789", dialCode: "49"), "+4915123456789")
        XCTAssertEqual(AuthViewModel.normalizedPhone("151 23456789", dialCode: "49"), "+4915123456789")
        XCTAssertEqual(AuthViewModel.normalizedPhone("0044 7700 900123", dialCode: "49"), "+447700900123")
        XCTAssertEqual(AuthViewModel.normalizedPhone("4155550123", dialCode: "1"), "+14155550123")
        XCTAssertNil(AuthViewModel.normalizedPhone("12", dialCode: "49"))
        XCTAssertNil(AuthViewModel.normalizedPhone("not a number", dialCode: "49"))
    }

    func testRequestCodeSuccessTransitionsToOTP() async {
        let mock = MockAuthService(startResult: .init(verificationID: "vid-9", channel: "sms", expiresInSeconds: 600))
        let vm = AuthViewModel(auth: mock)
        vm.phoneNumber = "+14155550123"
        await vm.requestCode()
        XCTAssertEqual(vm.step, .otp)
        XCTAssertEqual(vm.verificationID, "vid-9")
        XCTAssertEqual(mock.startedPhone, "+14155550123")
        XCTAssertNil(vm.errorMessage)
        XCTAssertEqual(vm.resendCountdown, 30)
    }

    func testRequestCodeInvalidPhoneShowsMessageAndStays() async {
        let vm = AuthViewModel(auth: MockAuthService())
        vm.phoneNumber = "xx"
        await vm.requestCode()
        XCTAssertEqual(vm.step, .welcome) // never advanced
        XCTAssertNotNil(vm.errorMessage)
    }

    func testRequestCodeBackendErrorMapsToHumanCopy() async {
        let mock = MockAuthService()
        mock.startError = APIError.api(code: "invalid_phone_number", message: "bad", retryable: false, requestID: nil)
        let vm = AuthViewModel(auth: mock)
        vm.begin() // user is on the phone-entry step
        vm.phoneNumber = "+14155550123"
        await vm.requestCode()
        XCTAssertEqual(vm.step, .phone) // stays on phone entry to retry
        XCTAssertEqual(vm.errorMessage, "That phone number doesn’t look right. Please check it and try again.")
    }

    func testConfirmSuccessCompletesAndCallsCallback() async {
        let session = Session(token: "tok-xyz", userID: "u-1", maskedNumber: "+14******123")
        let mock = MockAuthService(session: session)
        let vm = AuthViewModel(auth: mock)
        var received: Session?
        vm.onAuthenticated = { received = $0 }
        vm.phoneNumber = "+14155550123"
        await vm.requestCode()
        vm.code = "123456"
        await vm.confirmCode()
        XCTAssertEqual(vm.step, .done)
        XCTAssertEqual(received?.token, "tok-xyz")
    }

    func testConfirmWrongCodeShowsMessage() async {
        let mock = MockAuthService()
        mock.confirmError = APIError.api(code: "validation_failed", message: "The verification code is incorrect.", retryable: false, requestID: nil)
        let vm = AuthViewModel(auth: mock)
        vm.phoneNumber = "+14155550123"
        await vm.requestCode()
        vm.code = "000000"
        await vm.confirmCode()
        XCTAssertEqual(vm.step, .otp)
        XCTAssertNotNil(vm.errorMessage)
    }

    func testEditPhoneNumberReturnsToPhoneStep() async {
        let vm = AuthViewModel(auth: MockAuthService())
        vm.phoneNumber = "+14155550123"
        await vm.requestCode()
        vm.editPhoneNumber()
        XCTAssertEqual(vm.step, .phone)
        XCTAssertNil(vm.verificationID)
    }

    func testTickCountsDownResend() {
        let vm = AuthViewModel(auth: MockAuthService())
        vm.phoneNumber = "+14155550123"
        let exp = expectation(description: "started")
        Task { await vm.requestCode(); exp.fulfill() }
        wait(for: [exp], timeout: 2)
        XCTAssertEqual(vm.resendCountdown, 30)
        for _ in 0..<5 { vm.tick() }
        XCTAssertEqual(vm.resendCountdown, 25)
    }

    func testResetReturnsToWelcome() async {
        let vm = AuthViewModel(auth: MockAuthService())
        vm.phoneNumber = "+14155550123"
        await vm.requestCode()
        vm.reset()
        XCTAssertEqual(vm.step, .welcome)
        XCTAssertTrue(vm.phoneNumber.isEmpty)
        XCTAssertNil(vm.verificationID)
    }
}
