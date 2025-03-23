# src/utils/repositories.py
from google.cloud import firestore


class RulesetRepository:
    """Data access layer for ruleset collection."""

    def __init__(self, db=None):
        self.db = db or firestore.Client()
        self.collection = self.db.collection("ruleSets")

    def get_by_id(self, ruleset_id):
        """Get a ruleset by ID.

        Args:
            ruleset_id (str): Ruleset ID

        Returns:
            dict: Ruleset document or None if not found
        """
        doc = self.collection.document(ruleset_id).get()
        if not doc.exists:
            return None

        ruleset = doc.to_dict()
        ruleset["id"] = doc.id

        # Format timestamps
        if ruleset.get("updatedAt"):
            try:
                ruleset["updated_at"] = ruleset["updatedAt"].strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                ruleset["updated_at"] = "Invalid timestamp"
        else:
            ruleset["updated_at"] = "Never"

        return ruleset

    def get_for_project(self, user_id, project_id):
        """Get all rulesets for a project.

        Args:
            user_id (str): User ID
            project_id (str): Project ID

        Returns:
            list: List of ruleset documents
        """
        query = (
            self.collection.where("userId", "==", user_id)
            .where("projectId", "==", project_id)
            .order_by("updatedAt", direction=firestore.Query.DESCENDING)
        )

        docs = query.get()
        return [self._format_ruleset(doc) for doc in docs]

    def create(self, user_id, project_id, name, description=""):
        """Create a new ruleset.

        Args:
            user_id (str): User ID
            project_id (str): Project ID
            name (str): Ruleset name
            description (str, optional): Ruleset description

        Returns:
            dict: Created ruleset document
        """
        ruleset = {
            "name": name,
            "description": description,
            "userId": user_id,
            "projectId": project_id,
            "rules": [],
            "isShared": False,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }

        _, ref = self.collection.add(ruleset)
        doc = ref.get()
        return self._format_ruleset(doc)

    def update(self, ruleset_id, data):
        """Update a ruleset.

        Args:
            ruleset_id (str): Ruleset ID
            data (dict): Fields to update

        Returns:
            bool: Success status
        """
        # Add updatedAt timestamp
        update_data = data.copy()
        update_data["updatedAt"] = firestore.SERVER_TIMESTAMP

        # Update document
        self.collection.document(ruleset_id).update(update_data)
        return True

    def delete(self, ruleset_id):
        """Delete a ruleset.

        Args:
            ruleset_id (str): Ruleset ID

        Returns:
            bool: Success status
        """
        # Delete all rules in the subcollection first
        rules_ref = self.collection.document(ruleset_id).collection("rules")
        self._delete_collection(rules_ref, 100)

        # Delete the ruleset document
        self.collection.document(ruleset_id).delete()
        return True

    def toggle_sharing(self, ruleset_id):
        """Toggle sharing status for a ruleset.

        Args:
            ruleset_id (str): Ruleset ID

        Returns:
            bool: New sharing status
        """
        # Get current status
        ruleset_doc = self.collection.document(ruleset_id).get()
        if not ruleset_doc.exists:
            return False

        ruleset = ruleset_doc.to_dict()
        is_shared = not ruleset.get("isShared", False)

        # Update sharing status
        update_data = {
            "isShared": is_shared,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }

        # Add sharedAt timestamp if newly shared
        if is_shared and not ruleset.get("sharedAt"):
            update_data["sharedAt"] = firestore.SERVER_TIMESTAMP

        # Update document
        self.collection.document(ruleset_id).update(update_data)

        return is_shared

    def verify_ownership(self, ruleset_id, user_id):
        """Verify if a user owns a ruleset.

        Args:
            ruleset_id (str): Ruleset ID
            user_id (str): User ID

        Returns:
            bool: True if user owns the ruleset
        """
        ruleset = self.get_by_id(ruleset_id)
        if not ruleset:
            return False

        return ruleset.get("userId") == user_id

    def _format_ruleset(self, doc):
        """Format a ruleset document.

        Args:
            doc: Firestore document

        Returns:
            dict: Formatted ruleset document
        """
        ruleset = doc.to_dict()
        ruleset["id"] = doc.id

        # Format timestamps
        if ruleset.get("updatedAt"):
            try:
                ruleset["updated_at"] = ruleset["updatedAt"].strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception:
                ruleset["updated_at"] = "Invalid timestamp"
        else:
            ruleset["updated_at"] = "Never"

        return ruleset

    def _delete_collection(self, collection_ref, batch_size):
        """Delete all documents in a collection in batches.

        Args:
            collection_ref: Firestore collection reference
            batch_size (int): Batch size
        """
        docs = collection_ref.limit(batch_size).stream()
        deleted = 0

        for doc in docs:
            doc.reference.delete()
            deleted += 1

        if deleted >= batch_size:
            # There might be more documents to delete
            return self._delete_collection(collection_ref, batch_size)


class RuleRepository:
    """Data access layer for rule subcollection."""

    def __init__(self, db=None):
        self.db = db or firestore.Client()

    def get_for_ruleset(self, ruleset_id):
        """Get all rules for a ruleset.

        Args:
            ruleset_id (str): Ruleset ID

        Returns:
            list: List of rule documents
        """
        rules_ref = (
            self.db.collection("ruleSets")
            .document(ruleset_id)
            .collection("rules")
            .order_by("order")
        )

        rules_docs = rules_ref.get()

        rules = []
        for doc in rules_docs:
            rule = doc.to_dict()
            rule["id"] = doc.id
            rules.append(rule)

        return rules

    def get_by_id(self, ruleset_id, rule_id):
        """Get a rule by ID.

        Args:
            ruleset_id (str): Ruleset ID
            rule_id (str): Rule ID

        Returns:
            dict: Rule document or None if not found
        """
        rule_doc = (
            self.db.collection("ruleSets")
            .document(ruleset_id)
            .collection("rules")
            .document(rule_id)
            .get()
        )

        if not rule_doc.exists:
            return None

        rule = rule_doc.to_dict()
        rule["id"] = rule_doc.id

        return rule

    def create(self, ruleset_id, user_id, rule_data):
        """Create a new rule.

        Args:
            ruleset_id (str): Ruleset ID
            user_id (str): User ID
            rule_data (dict): Rule data

        Returns:
            dict: Created rule document
        """
        # Get current rule count for ordering
        existing_rules = self.get_for_ruleset(ruleset_id)

        # Prepare rule document
        new_rule = {
            "message": rule_data.get("message"),
            "severity": rule_data.get("severity"),
            "conditions": rule_data.get("conditions", []),
            "rulesetId": ruleset_id,
            "userId": user_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "order": len(existing_rules),  # Set order for sorting
        }

        # Add to rules subcollection
        _, rule_ref = (
            self.db.collection("ruleSets")
            .document(ruleset_id)
            .collection("rules")
            .add(new_rule)
        )

        # Update parent ruleset's updatedAt field
        self.db.collection("ruleSets").document(ruleset_id).update(
            {"updatedAt": firestore.SERVER_TIMESTAMP}
        )

        # Get the created document
        rule_doc = rule_ref.get()
        result = rule_doc.to_dict()
        result["id"] = rule_doc.id

        return result

    def update(self, ruleset_id, rule_id, data):
        """Update a rule.

        Args:
            ruleset_id (str): Ruleset ID
            rule_id (str): Rule ID
            data (dict): Fields to update

        Returns:
            bool: Success status
        """
        # Add updatedAt timestamp
        update_data = data.copy()
        update_data["updatedAt"] = firestore.SERVER_TIMESTAMP

        # Update document
        self.db.collection("ruleSets").document(ruleset_id).collection(
            "rules"
        ).document(rule_id).update(update_data)

        # Update parent ruleset's updatedAt field
        self.db.collection("ruleSets").document(ruleset_id).update(
            {"updatedAt": firestore.SERVER_TIMESTAMP}
        )

        return True

    def delete(self, ruleset_id, rule_id):
        """Delete a rule.

        Args:
            ruleset_id (str): Ruleset ID
            rule_id (str): Rule ID

        Returns:
            bool: Success status
        """
        # Delete document
        self.db.collection("ruleSets").document(ruleset_id).collection(
            "rules"
        ).document(rule_id).delete()

        # Update parent ruleset's updatedAt field
        self.db.collection("ruleSets").document(ruleset_id).update(
            {"updatedAt": firestore.SERVER_TIMESTAMP}
        )

        # Optionally, reorder remaining rules
        self.reorder_rules(ruleset_id)

        return True

    def reorder_rules(self, ruleset_id):
        """Reorder rules after deletion to maintain sequential order.

        Args:
            ruleset_id (str): Ruleset ID
        """
        # Get all rules sorted by current order
        rules_ref = (
            self.db.collection("ruleSets")
            .document(ruleset_id)
            .collection("rules")
            .order_by("order")
        )

        rules_docs = rules_ref.get()

        # Update order for each rule
        batch = self.db.batch()
        for i, doc in enumerate(rules_docs):
            rule_ref = (
                self.db.collection("ruleSets")
                .document(ruleset_id)
                .collection("rules")
                .document(doc.id)
            )
            batch.update(rule_ref, {"order": i})

        # Commit batch update
        batch.commit()
