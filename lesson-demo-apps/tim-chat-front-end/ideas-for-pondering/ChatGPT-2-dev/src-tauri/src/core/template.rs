use anyhow::{Context, Result};
use log::{error, info};
use regex::Regex;
use semver::Version;
use serde_json::json;
use std::{
    fs::{self, File},
    io::{Read, Write},
    path::Path,
};

pub static SCRIPT_ASK: &[u8] = include_bytes!("../../scripts/ask.js");

/// Struct representing the template with the script data.
#[derive(Debug)]
pub struct Template {
    pub ask: Vec<u8>,
}

impl Template {
    /// Creates a new Template instance, initializing it with the script data.
    pub fn new<P: AsRef<Path>>(template_dir: P) -> Self {
        let template_dir = template_dir.as_ref();
        let mut template = Template::default();

        let files = vec![(template_dir.join("ask.js"), &mut template.ask)];

        for (filename, _) in files {
            match update_or_create_file(&filename, SCRIPT_ASK) {
                Ok(updated) => {
                    if updated {
                        info!("Script updated or created: {}", filename.display());
                    } else {
                        info!("Script is up-to-date: {}", filename.display());
                    }
                }
                Err(e) => {
                    error!("Failed to process script, {}: {}", filename.display(), e);
                }
            }
        }

        template
    }
}

impl Default for Template {
    fn default() -> Template {
        Template {
            ask: Vec::from(SCRIPT_ASK),
        }
    }
}

/// Reads the version information from the given data.
fn read_version_info(data: &[u8]) -> Result<serde_json::Value> {
    let content = String::from_utf8_lossy(data);
    let re_name = Regex::new(r"@name\s+(.*?)\n").context("Failed to compile name regex")?;
    let re_version =
        Regex::new(r"@version\s+(.*?)\n").context("Failed to compile version regex")?;
    let re_url = Regex::new(r"@url\s+(.*?)\n").context("Failed to compile url regex")?;

    let name = re_name
        .captures(&content)
        .and_then(|cap| cap.get(1))
        .map_or(String::new(), |m| m.as_str().trim().to_string());

    let version = re_version
        .captures(&content)
        .and_then(|cap| cap.get(1))
        .map_or(String::new(), |m| m.as_str().trim().to_string());

    let url = re_url
        .captures(&content)
        .and_then(|cap| cap.get(1))
        .map_or(String::new(), |m| m.as_str().trim().to_string());

    let json_data = json!({
        "name": name,
        "version": version,
        "url": url,
    });

    Ok(json_data)
}

/// Reads the contents of the given file.
fn read_file_contents<P: AsRef<Path>>(filename: P) -> Result<Vec<u8>> {
    let filename = filename.as_ref();
    let mut file = File::open(filename)?;
    let mut contents = Vec::new();
    file.read_to_end(&mut contents)?;
    Ok(contents)
}

/// Writes the given data to the specified file.
fn write_file_contents<P: AsRef<Path>>(filename: P, data: &[u8]) -> Result<()> {
    let filename = filename.as_ref();
    let mut file = File::create(filename)?;
    file.write_all(data)?;
    Ok(())
}

/// Creates the necessary directories for the specified file path.
fn create_dir<P: AsRef<Path>>(filename: P) -> Result<()> {
    let filename = filename.as_ref();
    if let Some(parent) = filename.parent() {
        if !parent.exists() {
            fs::create_dir_all(parent)?;
        }
    }
    Ok(())
}

/// Updates the file if the new data has a newer version or if version info is missing,
/// or creates the file if it doesn't exist.
fn update_or_create_file<P: AsRef<Path>>(filename: P, new_data: &[u8]) -> Result<bool> {
    let filename = filename.as_ref();

    // Ensure directory exists
    create_dir(filename)?;

    let current_data = read_file_contents(filename);

    match current_data {
        Ok(current_data) => {
            let new_info = read_version_info(new_data)?;
            let current_info = read_version_info(&current_data);

            match (
                new_info.get("version").and_then(|v| v.as_str()),
                current_info,
            ) {
                (Some(new_version), Ok(current_info)) => {
                    let current_version = current_info
                        .get("version")
                        .and_then(|v| v.as_str())
                        .unwrap_or("");

                    if current_version.is_empty()
                        || Version::parse(new_version)? > Version::parse(current_version)?
                    {
                        write_file_contents(filename, new_data)?;
                        info!("{} → {}", current_version, new_version);
                        Ok(true)
                    } else {
                        Ok(false)
                    }
                }
                // If there is an error reading current version info, update the file
                (Some(_), Err(_)) => {
                    write_file_contents(filename, new_data)?;
                    Ok(true)
                }
                (None, _) => {
                    // If there is an error reading new version info, don't update the file
                    Ok(false)
                }
            }
        }
        Err(_) => {
            // If there is an error reading the current file, create a new file
            write_file_contents(filename, new_data)?;
            Ok(true)
        }
    }
}
