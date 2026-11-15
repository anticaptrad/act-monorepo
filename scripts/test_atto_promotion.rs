//! Rust-only gate for unverified AttoLang candidates and immutable gitlinks.
//! Does not assert Atto compiler execution or read live upstream PR state.
use std::process::Command;

const MANIFEST: &str = include_str!("../docs/atto-candidate-promotion.v1.json");
const MODULES: &str = include_str!("../.gitmodules");
const PINS: &[(&str, &str)] = &[
    ("packages/act-clients", "149b1af3be7447f2babf3fbcc1e45289f0d492b7"),
    ("packages/act-interfaces", "611828bcd6ceee863914854805d252e8ecbf871a"),
];

fn manifest_errors(value: &str) -> Vec<&'static str> {
    let required = [
        ("\"schema\": \"anticaptrad.atto-candidate-promotion/v1\"", "schema"),
        ("\"status\": \"candidate\"", "candidate status"),
        ("\"allowDeploy\": false", "deployment blocked"),
        ("\"allowSdkPublish\": false", "SDK release blocked"),
        ("\"requireExecutableCompilerReceipt\": true", "executable receipt"),
        ("\"requirePeerSchemaParity\": true", "peer schema parity"),
        ("\"anticaptrad/act-interfaces\"", "interface authority"),
        ("\"anticaptrad/act-clients\"", "client authority"),
        ("https://github.com/anticaptrad/act-interfaces/pull/18", "interface PR"),
        ("https://github.com/anticaptrad/act-clients/pull/26", "client PR"),
    ];
    let mut errors: Vec<_> = required.iter().filter_map(|(needle, error)| {
        if value.contains(needle) { None } else { Some(*error) }
    }).collect();
    for (path, sha) in PINS {
        if !value.contains(&format!("\"{path}\": \"{sha}\"")) {
            errors.push("immutable manifest pin");
        }
    }
    errors
}

fn gitlink(path: &str) -> Option<String> {
    let output = Command::new("git")
        .args(["ls-tree", "HEAD", "--", path])
        .output()
        .ok()?;
    if !output.status.success() { return None; }
    let text = String::from_utf8(output.stdout).ok()?;
    let parts: Vec<&str> = text.split_whitespace().collect();
    if parts.len() < 4 || parts[0] != "160000" || parts[1] != "commit" {
        return None;
    }
    if parts[2].len() != 40 || !parts[2].bytes().all(|b| b.is_ascii_hexdigit()) {
        return None;
    }
    Some(parts[2].to_owned())
}

#[test]
fn candidate_promotion_is_blocked_and_gitlinks_are_unchanged() {
    assert!(manifest_errors(MANIFEST).is_empty(), "{:?}", manifest_errors(MANIFEST));
    for (path, sha) in PINS {
        let repo = path.rsplit_once('/').expect("package path").1;
        assert!(MODULES.contains(&format!("[submodule \"{path}\"]")));
        assert!(MODULES.contains(&format!("https://github.com/anticaptrad/{repo}.git")));
        assert_eq!(gitlink(path).as_deref(), Some(*sha), "unexpected gitlink movement");
    }
    assert!(!MODULES.contains("atto-candidate"));
}

#[test]
fn negative_mutants_reject_premature_promotion_and_unverified_gitlink() {
    for (old, new) in [
        ("\"allowDeploy\": false", "\"allowDeploy\": true"),
        ("\"allowSdkPublish\": false", "\"allowSdkPublish\": true"),
        ("\"status\": \"candidate\"", "\"status\": \"production\""),
        ("\"requireExecutableCompilerReceipt\": true", "\"requireExecutableCompilerReceipt\": false"),
        ("\"requirePeerSchemaParity\": true", "\"requirePeerSchemaParity\": false"),
        ("149b1af3be7447f2babf3fbcc1e45289f0d492b7", "0000000000000000000000000000000000000000"),
    ] {
        let mutant = MANIFEST.replacen(old, new, 1);
        assert!(!manifest_errors(&mutant).is_empty(), "mutation escaped: {old}");
    }
}
