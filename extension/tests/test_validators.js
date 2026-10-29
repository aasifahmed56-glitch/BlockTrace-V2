// Extension Validation Unit Tests
// Tests address validation, hash normalization, and file header checks.

const assert = require('assert');

// 1. Ethereum Address Validator
function validateEthereumAddress(address) {
  if (!address || typeof address !== 'string') return false;
  return /^0x[a-fA-F0-9]{40}$/.test(address.trim());
}

// 2. Investigation Hash Normalizer & Validator
function normalizeHash(hash) {
  if (!hash) return '';
  let cleaned = hash.trim().toLowerCase();
  if (cleaned.startsWith('0x')) {
    cleaned = cleaned.slice(2);
  }
  return cleaned;
}

function validateInvestigationHash(hash) {
  if (!hash) return true;
  const cleaned = normalizeHash(hash);
  return /^[a-f0-9]{64}$/.test(cleaned);
}

// 3. PDF Header Validator (buffer/bytes)
function validatePdfBytes(buffer) {
  const MAX_FILE_SIZE = 25 * 1024 * 1024;
  if (!buffer || buffer.length === 0) {
    return { valid: false, error: 'Empty file' };
  }
  if (buffer.length > MAX_FILE_SIZE) {
    return { valid: false, error: 'File size exceeds 25 MB limit' };
  }
  const header = buffer.slice(0, 4).toString('ascii');
  if (header !== '%PDF') {
    return { valid: false, error: 'Missing %PDF magic header' };
  }
  return { valid: true };
}

console.log('Running Extension Validator Tests...');

// Address tests
assert.strictEqual(validateEthereumAddress('0x098B716B8Aaf21512996dC57EB0615e2383E2f96'), true, 'Valid mixed-case address');
assert.strictEqual(validateEthereumAddress('0x098b716b8aaf21512996dc57eb0615e2383e2f96'), true, 'Valid lowercase address');
assert.strictEqual(validateEthereumAddress('0x098B716B8AAF21512996DC57EB0615E2383E2F96'), true, 'Valid uppercase address');
assert.strictEqual(validateEthereumAddress('0xINVALID'), false, 'Invalid chars');
assert.strictEqual(validateEthereumAddress('098B716B8Aaf21512996dC57EB0615e2383E2f96'), false, 'Missing 0x prefix');
assert.strictEqual(validateEthereumAddress('0x098B716B8Aaf21512996dC57EB0615e2383E2f9'), false, 'Too short (39 chars)');
assert.strictEqual(validateEthereumAddress('0x098B716B8Aaf21512996dC57EB0615e2383E2f96aa'), false, 'Too long (42 chars)');
assert.strictEqual(validateEthereumAddress(''), false, 'Empty string');
assert.strictEqual(validateEthereumAddress(null), false, 'Null check');

// Hash tests
const valid64 = 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2';
assert.strictEqual(validateInvestigationHash(valid64), true, 'Valid 64-hex');
assert.strictEqual(validateInvestigationHash('0x' + valid64), true, 'Valid 64-hex with 0x prefix');
assert.strictEqual(validateInvestigationHash(valid64.toUpperCase()), true, 'Valid uppercase 64-hex');
assert.strictEqual(validateInvestigationHash(''), true, 'Optional empty hash');
assert.strictEqual(validateInvestigationHash('12345'), false, 'Too short hash');
assert.strictEqual(validateInvestigationHash(valid64 + '00'), false, 'Too long hash');
assert.strictEqual(validateInvestigationHash('z' + valid64.slice(1)), false, 'Non-hex char in hash');

// Normalizer
assert.strictEqual(normalizeHash('0x' + valid64), valid64, 'Strip 0x');
assert.strictEqual(normalizeHash('  0X' + valid64 + '  '), valid64, 'Trim and strip 0X');

// PDF Byte validator
assert.strictEqual(validatePdfBytes(Buffer.from('%PDF-1.4\n...')).valid, true, 'Valid PDF header');
assert.strictEqual(validatePdfBytes(Buffer.from('NOT_A_PDF')).valid, false, 'Invalid header');
assert.strictEqual(validatePdfBytes(Buffer.alloc(26 * 1024 * 1024)).valid, false, 'Oversized buffer');

console.log('All 18 validator tests PASSED successfully.');

