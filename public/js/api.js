/**
 * api.js
 * Centralized API client with authentication support
 */

class ApiClient {
  /**
   * Create a new API client
   * @param {Object} options - Configuration options
   * @param {number} options.timeout - Default timeout for requests in milliseconds
   */
  constructor(options = {}) {
    this.timeout = options.timeout || 200;
    this.authTokenProvider = options.authTokenProvider || (() => null);
  }

  /**
   * Fetch data with authentication
   * @param {string} url - API endpoint URL
   * @param {Object} options - Fetch options
   * @returns {Promise<any>} - Response data
   */
  async fetchWithAuth(url, options = {}) {
    try {
      const token = await this.authTokenProvider();

      if (!token) {
        throw new Error('No authentication token available');
      }

      const requestOptions = {
        ...options,
        headers: {
          ...(options.headers || {}),
          Authorization: `Bearer ${token}`,
        },
      };

      // Add small delay to ensure token is properly set
      await this._delay(this.timeout);

      const response = await fetch(url, requestOptions);

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }

      return await response.text();
    } catch (error) {
      console.error('API request failed:', error);
      this._showToast(`Error: ${error.message}`, true);
      throw error;
    }
  }

  /**
   * Post form data with authentication
   * @param {string} url - API endpoint URL
   * @param {FormData} formData - Form data to submit
   * @param {string} method - HTTP method (default: 'POST')
   * @param {string} targetSelector - CSS selector to update with response (optional)
   * @returns {Promise<string>} - Response text
   */
  async postFormWithAuth(
    url,
    formData,
    method = 'POST',
    targetSelector = null
  ) {
    try {
      const token = await this.authTokenProvider();

      if (!token) {
        throw new Error('No authentication token available');
      }

      const options = {
        method: method,
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      };

      // Add small delay to ensure token is properly set
      await this._delay(this.timeout);

      const response = await fetch(url, options);

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const responseText = await response.text();

      // Update the target if provided
      if (targetSelector && responseText) {
        const element = document.querySelector(targetSelector);
        if (element) {
          element.innerHTML = responseText;
        }
      }

      return responseText;
    } catch (error) {
      console.error('API form submission failed:', error);
      this._showToast(`Error: ${error.message}`, true);
      throw error;
    }
  }

  /**
   * Delete resource with authentication
   * @param {string} url - API endpoint URL
   * @param {string} targetSelector - CSS selector to update or remove (optional)
   * @returns {Promise<boolean>} - Success status
   */
  async deleteWithAuth(url, targetSelector = null) {
    try {
      const token = await this.authTokenProvider();

      if (!token) {
        throw new Error('No authentication token available');
      }

      const options = {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      };

      // Add small delay to ensure token is properly set
      await this._delay(this.timeout);

      const response = await fetch(url, options);

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      // Handle different status codes
      if (response.status === 204) {
        // No content - remove the target element if provided
        if (targetSelector) {
          const element = document.querySelector(targetSelector);
          if (element) element.remove();
        }
      } else if (response.status === 200) {
        // OK with content - update the target element if provided
        const responseText = await response.text();
        if (targetSelector && responseText) {
          const element = document.querySelector(targetSelector);
          if (element) element.innerHTML = responseText;
        }
      }

      return true;
    } catch (error) {
      console.error('API delete failed:', error);
      this._showToast(`Error: ${error.message}`, true);
      throw error;
    }
  }

  /**
   * Update resource with authentication
   * @param {string} url - API endpoint URL
   * @param {FormData|Object} data - Data to update
   * @param {string} targetSelector - CSS selector to update with response (optional)
   * @returns {Promise<string>} - Response text
   */
  async updateWithAuth(url, data, targetSelector = null) {
    // If data is not FormData, convert it to FormData
    let formData = data;
    if (!(data instanceof FormData)) {
      formData = new FormData();
      Object.entries(data).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    return this.postFormWithAuth(url, formData, 'PUT', targetSelector);
  }

  /**
   * Patch resource with authentication
   * @param {string} url - API endpoint URL
   * @param {FormData|Object} data - Data to patch
   * @param {string} targetSelector - CSS selector to update with response (optional)
   * @returns {Promise<string>} - Response text
   */
  async patchWithAuth(url, data, targetSelector = null) {
    // If data is not FormData, convert it to FormData
    let formData = data;
    if (!(data instanceof FormData)) {
      formData = new FormData();
      Object.entries(data).forEach(([key, value]) => {
        formData.append(key, value);
      });
    }

    return this.postFormWithAuth(url, formData, 'PATCH', targetSelector);
  }

  /**
   * Load HTML content with authentication and render it to a target element
   * @param {string} url - API endpoint URL
   * @param {string} targetSelector - CSS selector to update with response
   * @param {string} method - HTTP method (default: 'GET')
   * @param {Object} options - Additional fetch options
   * @param {Function} afterRender - Callback to run after rendering (optional)
   * @returns {Promise<void>}
   */
  async loadAndRender(
    url,
    targetSelector,
    method = 'GET',
    options = {},
    afterRender = null
  ) {
    try {
      const html = await this.fetchWithAuth(url, { method, ...options });

      const target = document.querySelector(targetSelector);
      if (!target) {
        console.warn(`Target ${targetSelector} not found.`);
        return;
      }

      target.innerHTML = html;

      if (afterRender && typeof afterRender === 'function') {
        afterRender();
      }
    } catch (error) {
      console.error('Load and render error:', error);
    }
  }

  /**
   * Internal helper to create a delay
   * @param {number} ms - Milliseconds to delay
   * @returns {Promise<void>}
   * @private
   */
  async _delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Internal helper to show a toast notification
   * @param {string} message - Message to display
   * @param {boolean} isError - Whether this is an error message
   * @private
   */
  _showToast(message, isError = false) {
    // Check if UI.showToast exists and use it
    if (window.UI && typeof window.UI.showToast === 'function') {
      window.UI.showToast(message, isError);
    } else {
      // Simple console fallback
      isError ? console.error(message) : console.info(message);
    }
  }
}

// Create default API client instance
const API = new ApiClient({
  timeout: 200,
  authTokenProvider: async () => {
    // Check if Auth module exists
    if (window.Auth && typeof window.Auth.getIdToken === 'function') {
      return await window.Auth.getIdToken();
    }
    // Fallback to App.currentFirebaseToken
    return window.App?.currentFirebaseToken || null;
  },
});

// Export both the class and default instance
export { ApiClient, API as default };
