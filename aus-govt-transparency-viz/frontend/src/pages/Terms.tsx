import React from 'react';

const Terms: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Terms of Use</h1>
      
      <div className="prose prose-lg text-gray-700">
        <p className="mb-4">
          Last Updated: {new Date().toLocaleDateString('en-AU', { year: 'numeric', month: 'long', day: 'numeric' })}
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Acceptance of Terms</h2>
        <p>
          By accessing or using the Australian Government Transparency Project website 
          ("the Service"), you agree to be bound by these Terms of Use. If you disagree 
          with any part of the terms, you do not have permission to access the Service.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Use License</h2>
        <p>
          The content on this website, including data, visualizations, text, graphics, 
          and software, is licensed under the Creative Commons Attribution 4.0 International 
          License (CC BY 4.0). This means you are free to:
        </p>
        <ul className="list-disc pl-6 space-y-2">
          <li>Share — copy and redistribute the material in any medium or format</li>
          <li>Adapt — remix, transform, and build upon the material for any purpose, even commercially</li>
        </ul>
        <p className="mt-4">
          Under the following terms:
        </p>
        <ul className="list-disc pl-6 space-y-2">
          <li>
            <strong>Attribution</strong> — You must give appropriate credit, provide a link to the 
            license, and indicate if changes were made. You may do so in any reasonable manner, 
            but not in any way that suggests the licensor endorses you or your use.
          </li>
        </ul>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Disclaimer</h2>
        <p>
          The information provided by the Service is for general informational purposes only. 
          All information on the site is provided in good faith, but we make no representation 
          or warranty of any kind, express or implied, regarding the accuracy, adequacy, validity, 
          reliability, availability, or completeness of any information on the site.
        </p>
        <p className="mt-4">
          The Service is not affiliated with the Australian Government or Parliament. We provide 
          access to publicly available information as a civic service to promote transparency.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Limitations</h2>
        <p>
          In no event shall the Australian Government Transparency Project, its operators, or any 
          of its affiliates be liable for any indirect, consequential, incidental, special, or 
          punitive damages, arising out of or in connection with your use of the Service.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">External Links</h2>
        <p>
          The Service may contain links to external websites that are not provided or maintained by 
          us. We do not guarantee the accuracy, relevance, timeliness, or completeness of any 
          information on these external websites.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Modifications</h2>
        <p>
          We reserve the right to modify or replace these Terms of Use at any time. If a revision is 
          material, we will provide at least 30 days' notice prior to any new terms taking effect. 
          What constitutes a material change will be determined at our sole discretion.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Governing Law</h2>
        <p>
          These Terms shall be governed and construed in accordance with the laws of Australia, 
          without regard to its conflict of law provisions.
        </p>
        
        <h2 className="text-xl font-semibold text-gray-800 mt-6 mb-3">Contact Us</h2>
        <p>
          If you have any questions about these Terms, please contact us at:
          <br />
          <a href="mailto:terms@ausgov-transparency.org" className="text-blue-600 hover:text-blue-800">
            terms@ausgov-transparency.org
          </a>
        </p>
      </div>
    </div>
  );
};

export default Terms; 