use numan_cli::core::registry::RegistryManager;
use std::error::Error;
use std::io::{Error as IoError, ErrorKind};
use std::path::Path;

fn main() -> Result<(), Box<dyn Error>> {
    let mut args = std::env::args_os().skip(1);
    let index_path = args.next().ok_or_else(|| {
        IoError::new(
            ErrorKind::InvalidInput,
            "usage: numan-registry-parser-check <index.json>",
        )
    })?;
    if args.next().is_some() {
        return Err(IoError::new(
            ErrorKind::InvalidInput,
            "usage: numan-registry-parser-check <index.json>",
        )
        .into());
    }

    let content = std::fs::read_to_string(&index_path)?;
    let manager = RegistryManager::new(Path::new("."))?;
    let index = manager.load_index_from_str(&content)?;
    if index.schema_version != 1 {
        return Err(IoError::new(
            ErrorKind::InvalidData,
            format!(
                "Numan parsed unsupported registry schema_version {}",
                index.schema_version
            ),
        )
        .into());
    }

    println!(
        "OK: Numan parsed schema v{} with {} package(s)",
        index.schema_version,
        index.packages.len()
    );
    Ok(())
}
