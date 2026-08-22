/**
 * @name Exposed secrets
 * @description Hardcoded credentials and secrets in code can lead to security vulnerabilities.
 * @kind problem
 * @problem.severity warning
 * @security-severity 8.0
 * @precision medium
 * @id js/exposed-secrets-exercise
 * @tags security
 *       external/cwe/cwe-798
 */

import javascript

/**
 * A string that might represent a secret or credential based on its name.
 */
predicate isPotentialSecretName(string name) {
  // TODO: Complete this predicate to identify variable names that might indicate secrets
  // HINT: Look for names containing terms like "password", "secret", "key", "token", etc.
  name.toLowerCase().matches("%password%") or
  false // Add more patterns
}

/**
 * A string literal that looks like a secret based on its format.
 */
predicate isPotentialSecretValue(string value) {
  // TODO: Complete this predicate to identify values that look like secrets
  // HINT: Consider patterns like hex strings, base64 encoded values, etc.
  (value.length() >= 16 and value.regexpMatch("[A-Za-z0-9+/=]{24,}")) or
  false // Add more patterns
}

from DataFlow::Node node
where
  // TODO: Complete the query to identify hardcoded secrets
  // HINT: Look for variable declarations, property writes, etc. with names and values 
  // matching the patterns above
  
  // This is a placeholder condition - replace with your implementation
  false
select node, "Potential hardcoded secret or credential found." 