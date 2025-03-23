# src/rulesets/ruleset_routes.py

from ..utils.auth_utils import require_auth, require_ruleset_ownership
from ..utils.repositories import RuleRepository, RulesetRepository
from ..utils.request_utils import extract_path_param, parse_form_data
from ..utils.response_utils import error_response, success_response

# Initialize repositories
ruleset_repo = RulesetRepository()
rule_repo = RuleRepository()


@require_auth()
def get_ruleset_edit_form(request):
    """Return HTML for editing a ruleset."""
    try:
        # Extract ruleset_id from path
        ruleset_id = extract_path_param(request.path, "/rulesets/")
        if not ruleset_id:
            ruleset_id = request.args.get("ruleset_id")

        if not ruleset_id:
            return error_response("Missing ruleset ID", status=400)

        # Get the ruleset
        ruleset = ruleset_repo.get_by_id(ruleset_id)
        if not ruleset:
            return error_response("Ruleset not found", status=404)

        # Verify ownership
        if ruleset.get("userId") != request.user_id:
            return error_response(
                "You don't have permission to edit this ruleset", status=403
            )

        # Get rules for this ruleset
        rules = rule_repo.get_for_ruleset(ruleset_id)

        # Return the template with both ruleset and rules
        return success_response(
            {"ruleset": ruleset, "rules": rules, "ruleset_id": ruleset_id},
            template="edit_ruleset.html",
        )
    except Exception as e:
        return error_response(f"Error loading ruleset: {str(e)}", status=500)


@require_auth()
def create_new_ruleset(request):
    """Create a new ruleset."""
    try:
        # Get form data
        form_data = parse_form_data(request)
        project_id = form_data.get("projectId")
        name = form_data.get("name")
        description = form_data.get("description", "")

        if not project_id or not name:
            return error_response("Missing required fields", status=400)

        # Create the ruleset
        ruleset = ruleset_repo.create(request.user_id, project_id, name, description)

        # Return the edit form for the new ruleset
        return success_response({"ruleset": ruleset}, template="edit_ruleset.html")
    except Exception as e:
        return error_response(f"Error creating ruleset: {str(e)}", status=500)


@require_ruleset_ownership()
def update_ruleset_info(request):
    """Update a ruleset's basic information."""
    try:
        # Extract ruleset_id from path or args
        ruleset_id = extract_path_param(request.path, "/rulesets/")
        if not ruleset_id:
            ruleset_id = request.args.get("ruleset_id")

        # Get form data
        form_data = parse_form_data(request)
        name = form_data.get("name")
        description = form_data.get("description", "")

        if not name:
            return error_response("Missing required fields", status=400)

        # Update the ruleset
        ruleset_repo.update(ruleset_id, {"name": name, "description": description})

        # Return to the edit form
        return get_ruleset_edit_form(request)

    except Exception as e:
        return error_response(f"Error updating ruleset: {str(e)}", status=500)


@require_ruleset_ownership()
def delete_ruleset_handler(request):
    """Delete a ruleset."""
    try:
        # Extract ruleset_id from path
        ruleset_id = extract_path_param(request.path, "/rulesets/", "/delete")
        if not ruleset_id:
            ruleset_id = request.args.get("ruleset_id")

        # request should be a DELETE request
        if request.method != "DELETE":
            return error_response("Invalid request method", status=405)

        # Delete the ruleset (repository will handle rule deletion)
        ruleset_repo.delete(ruleset_id)

        # Return empty response
        return success_response(status=204)

    except Exception as e:
        return error_response(f"Error deleting ruleset: {str(e)}", status=500)


@require_ruleset_ownership()
def toggle_ruleset_sharing_handler(request):
    """Toggle sharing status for a ruleset."""
    try:
        # Extract ruleset_id from path
        ruleset_id = extract_path_param(request.path, "/rulesets/", "/share")
        if not ruleset_id:
            ruleset_id = request.args.get("ruleset_id")

        # Toggle the sharing status
        ruleset_repo.toggle_sharing(ruleset_id)

        # Get updated ruleset
        ruleset = ruleset_repo.get_by_id(ruleset_id)
        ruleset["rules"] = rule_repo.get_for_ruleset(ruleset_id)

        # Get host URL for generating shared links
        host_url = request.headers.get("Host", "")
        if not host_url.startswith("http"):
            protocol = (
                "https"
                if not ("localhost" in host_url or "127.0.0.1" in host_url)
                else "http"
            )
            location_origin = f"{protocol}://{host_url}"
        else:
            location_origin = host_url

        # Return the updated status
        return success_response(
            {"location_origin": location_origin, "ruleset": ruleset},
            template="ruleset_card.html",
        )
    except Exception as e:
        return error_response(f"Error toggling sharing: {str(e)}", status=500)
