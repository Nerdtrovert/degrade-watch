/**
 * API error handling utilities
 */
import type { AxiosError } from 'axios';

/**
 * Sanitize error data before logging to avoid exposing sensitive information
 */
export const sanitizeErrorData = (data: any): any => {
  if (!data) return data;

  // Create a copy to avoid modifying the original
  const sanitized = { ...data };

  // Remove potentially sensitive fields
  const sensitiveFields = ['password', 'token', 'authorization', 'secret', 'key'];
  sensitiveFields.forEach(field => {
    if (sanitized[field]) {
      sanitized[field] = '[REDACTED]';
    }
    if (sanitized[field.toUpperCase()]) {
      sanitized[field.toUpperCase()] = '[REDACTED]';
    }
    if (sanitized[field.toLowerCase()]) {
      sanitized[field.toLowerCase()] = '[REDACTED]';
    }
  });

  return sanitized;
};

/**
 * Handle API errors with proper logging and error categorization
 */
export const handleApiError = (error: AxiosError): Promise<never> => {
  if (error.response) {
    // The request was made and the server responded with a status code
    // that falls out of the range of 2xx
    if (import.meta.env.DEV) {
      console.error(
        `API Error: ${error.response.status}`,
        sanitizeErrorData(error.response.data)
      );
    } else {
      console.error(`API Error: ${error.response.status}`);
    }

    // Handle specific status codes
    if (error.response.status === 401 || error.response.status === 403) {
      // Auth error handling - clear auth data and redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_roles');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    // Add other status code handling as needed
  } else if (error.request) {
    // The request was made but no response was received
    if (import.meta.env.DEV) {
      console.error('API Error: No response received', error.request);
    } else {
      console.error('API Error: No response received');
    }
  } else {
    // Something happened in setting up the request that triggered an Error
    if (import.meta.env.DEV) {
      console.error('API Error: Request setup failed', error.message);
    } else {
      console.error('API Error: Request setup failed');
    }
  }

  return Promise.reject(error);
};