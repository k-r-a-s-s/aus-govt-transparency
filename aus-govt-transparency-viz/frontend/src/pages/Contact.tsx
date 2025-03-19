import React, { useState } from 'react';

type FormState = {
  name: string;
  email: string;
  subject: string;
  message: string;
};

type FormErrors = {
  [key in keyof FormState]?: string;
};

const Contact: React.FC = () => {
  const [formData, setFormData] = useState<FormState>({
    name: '',
    email: '',
    subject: '',
    message: ''
  });
  
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }
    
    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email is invalid';
    }
    
    if (!formData.subject.trim()) {
      newErrors.subject = 'Subject is required';
    }
    
    if (!formData.message.trim()) {
      newErrors.message = 'Message is required';
    } else if (formData.message.length < 10) {
      newErrors.message = 'Message must be at least 10 characters long';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    // Clear error when user starts typing
    if (errors[name as keyof FormState]) {
      setErrors(prev => ({
        ...prev,
        [name]: undefined
      }));
    }
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    setSubmitStatus('idle');
    
    // Simulate API call
    try {
      // In a real application, you would post to your backend API
      // await axios.post('/api/contact', formData);
      
      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // Reset form after successful submission
      setFormData({
        name: '',
        email: '',
        subject: '',
        message: ''
      });
      
      setSubmitStatus('success');
    } catch (error) {
      console.error('Error submitting form:', error);
      setSubmitStatus('error');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">Contact Us</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
          <p className="text-lg text-gray-700 mb-6">
            We value your feedback and questions about the Australian Government Transparency Project. 
            Please use this form to get in touch with our team.
          </p>
          
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
            <p className="text-blue-700">
              <strong>Note:</strong> This is a public interest project. For media inquiries or 
              collaboration opportunities, please indicate this in your message.
            </p>
          </div>
          
          <div className="mt-8">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Other Ways to Connect</h2>
            
            <div className="space-y-4">
              <div>
                <h3 className="font-medium text-gray-800">Email</h3>
                <p className="text-gray-600">
                  <a href="mailto:contact@ausgov-transparency.org" className="text-blue-600 hover:text-blue-800">
                    contact@ausgov-transparency.org
                  </a>
                </p>
              </div>
              
              <div>
                <h3 className="font-medium text-gray-800">Twitter</h3>
                <p className="text-gray-600">
                  <a href="https://twitter.com/AusGovTransparency" className="text-blue-600 hover:text-blue-800" target="_blank" rel="noopener noreferrer">
                    @AusGovTransparency
                  </a>
                </p>
              </div>
              
              <div>
                <h3 className="font-medium text-gray-800">GitHub</h3>
                <p className="text-gray-600">
                  <a href="https://github.com/username/aus-govt-transparency" className="text-blue-600 hover:text-blue-800" target="_blank" rel="noopener noreferrer">
                    aus-govt-transparency
                  </a>
                </p>
              </div>
            </div>
          </div>
        </div>
        
        <div>
          <form onSubmit={handleSubmit} className="bg-white shadow-md rounded-lg p-6">
            {submitStatus === 'success' && (
              <div className="mb-6 bg-green-50 border border-green-200 text-green-800 rounded-md p-4">
                <p className="font-medium">Thank you for your message!</p>
                <p>We've received your inquiry and will get back to you soon.</p>
              </div>
            )}
            
            {submitStatus === 'error' && (
              <div className="mb-6 bg-red-50 border border-red-200 text-red-800 rounded-md p-4">
                <p className="font-medium">Something went wrong!</p>
                <p>We couldn't send your message. Please try again later or contact us directly via email.</p>
              </div>
            )}
            
            <div className="mb-4">
              <label htmlFor="name" className="block text-gray-700 font-medium mb-2">
                Your Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                  errors.name ? 'border-red-500 focus:ring-red-200' : 'border-gray-300 focus:ring-blue-200'
                }`}
                placeholder="Jane Doe"
              />
              {errors.name && <p className="mt-1 text-red-500 text-sm">{errors.name}</p>}
            </div>
            
            <div className="mb-4">
              <label htmlFor="email" className="block text-gray-700 font-medium mb-2">
                Email Address <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                  errors.email ? 'border-red-500 focus:ring-red-200' : 'border-gray-300 focus:ring-blue-200'
                }`}
                placeholder="jane.doe@example.com"
              />
              {errors.email && <p className="mt-1 text-red-500 text-sm">{errors.email}</p>}
            </div>
            
            <div className="mb-4">
              <label htmlFor="subject" className="block text-gray-700 font-medium mb-2">
                Subject <span className="text-red-500">*</span>
              </label>
              <select
                id="subject"
                name="subject"
                value={formData.subject}
                onChange={handleChange}
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                  errors.subject ? 'border-red-500 focus:ring-red-200' : 'border-gray-300 focus:ring-blue-200'
                }`}
              >
                <option value="">Please select a subject</option>
                <option value="General Inquiry">General Inquiry</option>
                <option value="Bug Report">Bug Report</option>
                <option value="Feature Request">Feature Request</option>
                <option value="Data Question">Data Question</option>
                <option value="Media Inquiry">Media Inquiry</option>
                <option value="Collaboration">Collaboration Opportunity</option>
              </select>
              {errors.subject && <p className="mt-1 text-red-500 text-sm">{errors.subject}</p>}
            </div>
            
            <div className="mb-4">
              <label htmlFor="message" className="block text-gray-700 font-medium mb-2">
                Your Message <span className="text-red-500">*</span>
              </label>
              <textarea
                id="message"
                name="message"
                value={formData.message}
                onChange={handleChange}
                rows={5}
                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 ${
                  errors.message ? 'border-red-500 focus:ring-red-200' : 'border-gray-300 focus:ring-blue-200'
                }`}
                placeholder="Please enter your message here..."
              ></textarea>
              {errors.message && <p className="mt-1 text-red-500 text-sm">{errors.message}</p>}
            </div>
            
            <button
              type="submit"
              disabled={isSubmitting}
              className={`w-full py-2 px-4 rounded-md text-white font-medium ${
                isSubmitting 
                  ? 'bg-blue-400 cursor-not-allowed' 
                  : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
              }`}
            >
              {isSubmitting ? 'Sending...' : 'Send Message'}
            </button>
            
            <p className="mt-4 text-sm text-gray-600">
              <span className="text-red-500">*</span> Required fields
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Contact; 