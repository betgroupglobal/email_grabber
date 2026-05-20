/**
 * Simple test script to verify API endpoints are accessible
 * This can be run with: node test-api.js
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_KNOWLEDGE_ENGINE_URL || 'http://localhost:8000';

async function testEndpoint(endpoint, method = 'GET', body = null) {
  try {
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

async function runTests() {
  console.log('Testing OpsecAI Backend API...\n');
  console.log(`API Base URL: ${API_BASE_URL}\n`);

  const tests = [
    {
      name: 'Health Check',
      endpoint: '/health',
      method: 'GET'
    },
    {
      name: 'Build Attack Tree',
      endpoint: '/attack-tree/build',
      method: 'POST',
      body: {
        target_description: 'Test web server for vulnerability assessment'
      }
    },
    {
      name: 'Get Agent Status',
      endpoint: '/agents/status',
      method: 'GET'
    }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    console.log(`Testing: ${test.name}`);
    const result = await testEndpoint(test.endpoint, test.method, test.body);
    
    if (result.success) {
      console.log(`✓ PASSED`);
      console.log(`  Response:`, JSON.stringify(result.data).substring(0, 100) + '...\n');
      passed++;
    } else {
      console.log(`✗ FAILED`);
      console.log(`  Error: ${result.error}\n`);
      failed++;
    }
  }

  console.log(`\nTest Results: ${passed} passed, ${failed} failed`);
  
  if (failed > 0) {
    console.log('\n❌ Some tests failed. Make sure the backend API is running.');
    process.exit(1);
  } else {
    console.log('\n✅ All tests passed!');
  }
}

runTests();