#if canImport(SwiftUI)
import SwiftUI

/// Picks the first name a caller may say, from the server's list only: nothing
/// typed here goes into a call, the search just finds the entry.
struct FirstNamePicker: View {
    @Bindable var vm: ProfileViewModel
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""

    var body: some View {
        List {
            Section {
                row(String(localized: "No name"), selected: vm.firstName == nil) { choose(nil) }
                ForEach(vm.firstNameResults, id: \.self) { name in
                    row(name, selected: name == vm.firstName) { choose(name) }
                }
            } footer: {
                if query.trimmingCharacters(in: .whitespaces).isEmpty {
                    Text("Type the first letters of your name. A caller may say it; without one, they don't use a name.")
                } else if vm.firstNameResults.isEmpty {
                    Text("This name isn't in our list yet. You can leave it empty.")
                }
            }
            if let error = vm.errorMessage {
                Section { ErrorBanner(error) }
            }
        }
        .bcSearchable(text: $query, prompt: Text("Search names"))
        .autocorrectionDisabled()
        .task(id: query) {
            try? await Task.sleep(for: .milliseconds(200))
            guard !Task.isCancelled else { return }
            await vm.searchFirstNames(query)
        }
        .bcClearScrollBackground()
        .bcScreenBackground()
        .navigationTitle("First name")
    }

    private func row(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title).foregroundStyle(.primary)
                Spacer()
                if selected {
                    Image(systemName: "checkmark")
                        .foregroundStyle(Theme.accent)
                        .accessibilityHidden(true)
                }
            }
        }
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func choose(_ name: String?) {
        Task {
            await vm.chooseFirstName(name)
            if vm.errorMessage == nil { dismiss() }
        }
    }
}
#endif
