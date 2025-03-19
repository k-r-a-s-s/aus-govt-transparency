import React from 'react';

const Privacy: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Privacy Policy</h1>
      
      <div className="prose prose-lg text-gray-700">
        <p className="mb-4">
          Last Updated: {new Date().toLocaleDateString('en-AU', { year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Overview</h2>
        <p>
          The Australian Government Transparency Project ("we", "us", or "our") is committed to protecting your privacy. 
          This Privacy Policy explains how we collect, use, and disclose information about visitors to our website.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Information We Collect</h2>
        <p>
          <strong>Usage Data:</strong> We collect anonymous usage data such as page views, referring websites,
          and user interactions with our site. This data helps us improve our service and understand how
          visitors use our platform.
        </p>
        <p>
          <strong>Cookies:</strong> We use cookies to enhance your experience on our site. These cookies
          are used to remember your preferences and provide analytics about site usage.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">How We Use Information</h2>
        <p>We use the information we collect to:</p>
        <ul className="list-disc pl-6 space-y-2">
          <li>Improve and optimize our website</li>
          <li>Analyze usage patterns and trends</li>
          <li>Detect and prevent security issues</li>
          <li>Respond to user inquiries and support requests</li>
        </ul>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Data Sharing</h2>
        <p>
          We do not sell or rent your personal information to third parties. We may share anonymous
          usage data with trusted analytics providers who help us understand how our site is used.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Public Data</h2>
        <p>
          Our service provides access to publicly available information about parliamentary disclosures.
          This information is already in the public domain and is made available as part of our commitment
          to transparency in governance.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Your Rights</h2>
        <p>
          You have the right to access, correct, or delete your personal information where applicable.
          If you have any questions about our privacy practices or would like to exercise these rights,
          please contact us at privacy@ausgov-transparency.org.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Changes to This Policy</h2>
        <p>
          We may update this Privacy Policy from time to time. We will notify users of any material
          changes by posting the new Privacy Policy on this page and updating the "Last Updated" date.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Contact Us</h2>
        <p>
          If you have any questions about this Privacy Policy, please contact us at:
          <br />
          <a href="mailto:privacy@ausgov-transparency.org" className="text-blue-600 hover:text-blue-800">
            privacy@ausgov-transparency.org
          </a>
        </p>
      </div>
    </div>
  );
};

export default Privacy; 