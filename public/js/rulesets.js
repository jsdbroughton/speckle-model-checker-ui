/**
 * rulesets.js
 * Handles ruleset-specific functionality
 */
import API from './api.js';

class RulesetComponent {
  /**
   * Navigate to the ruleset edit page
   * @param {string} rulesetId - Ruleset ID to edit
   * @param {Event} event - Optional event to prevent default behavior
   */
  async goToRuleset(rulesetId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      await API.loadAndRender(`/api/rulesets/${rulesetId}`, '#main-content');

      // Update URL in browser history
      history.pushState({}, '', `/rulesets/${rulesetId}`);
    } catch (error) {
      console.error('Failed to navigate to ruleset:', error);
    }
  }

  /**
   * Delete a ruleset
   * @param {string} rulesetId - Ruleset ID to delete
   * @param {Event} event - Optional event to prevent default behavior
   */
  async deleteRuleset(rulesetId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    // Confirm deletion
    if (!confirm('Are you sure you want to delete this ruleset?')) {
      return;
    }

    try {
      await API.deleteWithAuth(
        `/api/rulesets/${rulesetId}/delete`,
        `#ruleset-card-${rulesetId}`
      );
      UI.showToast('Ruleset deleted successfully');
    } catch (error) {
      console.error('Failed to delete ruleset:', error);
    }
  }

  /**
   * Toggle sharing status for a ruleset
   * @param {string} rulesetId - Ruleset ID
   * @param {Event} event - Optional event to prevent default behavior
   */
  async toggleRulesetSharing(rulesetId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      const html = await API.patchWithAuth(
        `/api/rulesets/${rulesetId}/share`,
        {},
        `#ruleset-card-${rulesetId}`
      );

      // Determine if ruleset is now shared or unshared
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const isShared =
        doc.querySelector('[data-shared]')?.dataset.shared === 'True';

      UI.showToast(
        isShared
          ? 'Ruleset shared successfully'
          : 'Ruleset unshared successfully'
      );
    } catch (error) {
      console.error('Failed to toggle sharing:', error);
    }
  }

  /**
   * Export ruleset
   * @param {string} rulesetId - Ruleset ID to export
   * @param {Event} event - Optional event to prevent default behavior
   */
  async exportRuleset(rulesetId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      // Create download link
      const a = document.createElement('a');
      a.href = `/api/rulesets/${rulesetId}/export`;
      a.download = `ruleset-${rulesetId}.tsv`;
      a.style.display = 'none';

      // Add to body, click, and remove
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      UI.showToast('Exporting ruleset');
    } catch (error) {
      console.error('Failed to export ruleset:', error);
    }
  }

  /**
   * Create a new rule form
   * @param {string} rulesetId - Ruleset ID
   * @param {Event} event - Optional event to prevent default behavior
   */
  async newRule(rulesetId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      await API.loadAndRender(
        `/api/rulesets/${rulesetId}/rules/new`,
        '#rule-form-container'
      );

      // Hide the button that was clicked
      if (event && event.target) {
        event.target.style.display = 'none';
      }

      // Update any severity dropdowns
      if (window.UI && typeof window.UI.updateSeverityColor === 'function') {
        window.UI.updateSeverityColor();
      }
    } catch (error) {
      console.error('Failed to load new rule form:', error);
    }
  }

  /**
   * Add a new rule
   * @param {string} rulesetId - Ruleset ID
   * @param {HTMLFormElement} form - Form element containing rule data
   * @param {Event} event - Form submission event
   */
  async addNewRule(rulesetId, form, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      const formData = new FormData(form);

      await API.postFormWithAuth(
        `/api/rulesets/${rulesetId}/rules`,
        formData,
        'POST',
        '#rules-container'
      );

      // Clear new rule form container
      document.getElementById('rule-form-container').innerHTML = '';

      UI.showToast('Rule added successfully');
    } catch (error) {
      console.error('Failed to add rule:', error);
    }

    return false;
  }

  /**
   * Edit a rule
   * @param {string} rulesetId - Ruleset ID
   * @param {string} ruleId - Rule ID
   * @param {Event} event - Click event
   */
  async editRule(rulesetId, ruleId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      // Get the current row
      const currentRow = event.target.closest('tr');
      const tbody = currentRow.parentElement;

      // Remove 'editing' class from all sibling rows
      Array.from(tbody.children).forEach((tr) => {
        if (tr !== currentRow) {
          tr.classList.remove('editing');
        }
      });

      // Add 'editing' class to current row
      currentRow.classList.add('editing');

      await API.loadAndRender(
        `/api/rulesets/${rulesetId}/rules/${ruleId}/edit`,
        '#rule-form-container'
      );

      // Update severity color
      if (window.UI && typeof window.UI.updateSeverityColor === 'function') {
        window.UI.updateSeverityColor();
      }
    } catch (error) {
      console.error('Failed to load edit form:', error);
    }
  }

  /**
   * Update a rule
   * @param {string} rulesetId - Ruleset ID
   * @param {string} ruleId - Rule ID
   * @param {HTMLFormElement} form - Form element containing rule data
   * @param {Event} event - Form submission event
   */
  async updateRule(rulesetId, ruleId, form, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      const formData = new FormData(form);

      await API.postFormWithAuth(
        `/api/rulesets/${rulesetId}/rules/${ruleId}`,
        formData,
        'PUT',
        '#rules-container'
      );

      // Clear rule form container
      document.getElementById('rule-form-container').innerHTML = '';

      UI.showToast('Rule updated successfully');
    } catch (error) {
      console.error('Failed to update rule:', error);
    }

    return false;
  }

  /**
   * Delete a rule
   * @param {string} rulesetId - Ruleset ID
   * @param {string} ruleId - Rule ID
   * @param {Event} event - Click event
   */
  async deleteRule(rulesetId, ruleId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    // Add class to show deletion spinner
    if (event && event.target) {
      event.target.closest('tr').classList.add('deleting');
    }

    // Confirm deletion
    if (!confirm('Are you sure you want to delete this rule?')) {
      // Remove deleting class if canceled
      if (event && event.target) {
        event.target.closest('tr').classList.remove('deleting');
      }
      return;
    }

    try {
      await API.deleteWithAuth(
        `/api/rulesets/${rulesetId}/rules/${ruleId}`,
        '#rules-container'
      );

      UI.showToast('Rule deleted successfully');
    } catch (error) {
      console.error('Failed to delete rule:', error);

      // Remove deleting class on error
      if (event && event.target) {
        event.target.closest('tr').classList.remove('deleting');
      }
    }
  }

  /**
   * Add condition row
   * @param {Event} event - Click event
   */
  async addConditionRow(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      const container = document.querySelector('#conditions-container');
      const index = container.querySelectorAll('.condition-row').length;

      const response = await fetch(`/api/rule/condition?index=${index}`);
      const html = await response.text();

      container.insertAdjacentHTML('beforeend', html);
    } catch (error) {
      console.error('Failed to add condition row:', error);
    }
  }

  /**
   * Delete condition row
   * @param {Event} event - Click event
   */
  deleteConditionRow(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    try {
      const row = event.target.closest('.condition-row');
      if (row) {
        row.remove();
      }
    } catch (error) {
      console.error('Failed to delete condition row:', error);
    }
  }
}

// Create a singleton instance
const Rulesets = new RulesetComponent();

// Export both the class and singleton instance
export { RulesetComponent, Rulesets as default };
