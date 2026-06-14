#if canImport(SwiftUI)
import SwiftUI

// The optional Save Contact flow, attached to the SMS success surface. None of
// this is on the critical send path: sender continuity comes from the backend
// binding whether or not a contact is ever saved.

#if canImport(ContactsUI) && canImport(UIKit)
import ContactsUI
import Contacts
import UIKit

/// A prefilled iOS "new contact" sheet. We only set a name and the bound sender
/// number — never a photo, address, email, or notes — and the user must confirm
/// with Done; Cancel saves nothing.
struct NewContactSheet: UIViewControllerRepresentable {
    let displayName: String
    let phoneE164: String
    let onFinish: (_ savedContactIdentifier: String?) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onFinish: onFinish) }

    func makeUIViewController(context: Context) -> UINavigationController {
        let contact = CNMutableContact()
        contact.givenName = displayName
        contact.phoneNumbers = [
            CNLabeledValue(label: CNLabelPhoneNumberMain,
                           value: CNPhoneNumber(stringValue: phoneE164)),
        ]
        let controller = CNContactViewController(forNewContact: contact)
        controller.delegate = context.coordinator
        controller.allowsActions = false
        return UINavigationController(rootViewController: controller)
    }

    func updateUIViewController(_ controller: UINavigationController, context: Context) {}

    final class Coordinator: NSObject, CNContactViewControllerDelegate {
        let onFinish: (String?) -> Void
        init(onFinish: @escaping (String?) -> Void) { self.onFinish = onFinish }

        func contactViewController(_ viewController: CNContactViewController,
                                   didCompleteWith contact: CNContact?) {
            // `contact` is non-nil only when the user tapped Done.
            onFinish(contact?.identifier)
        }
    }
}
#endif

extension View {
    /// Attaches the post-success Save Contact prompt, the prefilled contact
    /// sheet, and the permission-denied notice to a host view.
    func saveContactFlow(vm: HomeViewModel) -> some View {
        modifier(SaveContactFlowModifier(vm: vm))
    }
}

private struct SaveContactFlowModifier: ViewModifier {
    @Bindable var vm: HomeViewModel

    func body(content: Content) -> some View {
        content
            // 1. Soft, non-blocking suggestion. The button actions use the
            // captured `sender` (not `pendingSenderPrompt`) so the alert's own
            // dismissal — which clears `pendingSenderPrompt` — can't race the
            // Save action and turn a "Save" into a no-op.
            .alert(
                "Save this sender as a contact?",
                isPresented: Binding(
                    get: { vm.pendingSenderPrompt != nil },
                    set: { if !$0 { vm.pendingSenderPrompt = nil } }
                ),
                presenting: vm.pendingSenderPrompt
            ) { sender in
                Button("Save Contact") { Task { await vm.beginSaveContact(for: sender) } }
                Button("Not now", role: .cancel) { vm.markPromptSkipped(for: sender) }
            } message: { sender in
                Text("Future texts from \(sender.displayName ?? "this sender") can come from the same sender. You can save this contact now or skip it.")
            }
            // 2. Prefilled contact sheet (presented only after permission).
            .sheet(item: $vm.contactSheetSender) { sender in
                contactSheet(for: sender)
            }
            // 3. Permission denied — explain that it's optional, offer Settings.
            .alert(
                "Saving contacts is optional",
                isPresented: Binding(
                    get: { vm.contactPermissionDeniedSender != nil },
                    set: { if !$0 { vm.dismissPermissionDeniedNotice() } }
                )
            ) {
                #if canImport(UIKit)
                Button("Open Settings") {
                    openSettings()
                    vm.dismissPermissionDeniedNotice()
                }
                #endif
                Button("OK", role: .cancel) { vm.dismissPermissionDeniedNotice() }
            } message: {
                Text("Contacts access is optional. You can still use this sender without saving a contact.")
            }
    }

    @ViewBuilder
    private func contactSheet(for sender: SenderIdentity) -> some View {
        #if canImport(ContactsUI) && canImport(UIKit)
        NewContactSheet(
            displayName: sender.displayName ?? "Contact",
            phoneE164: sender.phoneE164 ?? ""
        ) { identifier in
            vm.contactSheetFinished(savedIdentifier: identifier)
        }
        .ignoresSafeArea()
        #else
        // No contact UI on this platform; treat as dismissed.
        Color.clear.onAppear { vm.contactSheetFinished(savedIdentifier: nil) }
        #endif
    }

    #if canImport(UIKit)
    private func openSettings() {
        guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
        UIApplication.shared.open(url)
    }
    #endif
}
#endif
