package com.leavems;

import java.time.LocalDate;

/** Dependency-free repository checks; run with java com.leavems.TaskWorkflowTest. */
public final class TaskWorkflowTest {
    public static void main(String[] args) {
        var repository = new LeaveManagementApp.MemoryRepository();
        var admin = repository.authenticate("admin", "admin123");
        var employee = repository.authenticate("Kavin", "Kavin");
        check(repository.findEmployees().size() == 20, "Twenty Tamil employee accounts are available");
        for (var person : repository.findEmployees()) {
            check(person.name().equals(person.username()) && !person.name().contains(" "), "Each employee has a single name and matching login ID");
            check(repository.authenticate(person.username(), person.name()) != null, "Each employee signs in with their name as the password");
        }
        check(repository.authenticate("employee", "employee123") == null, "Old shared credentials are retired");
        check(repository.authenticate("Kavin", "kavin") == null, "Passwords are case-sensitive");
        check(repository.findTasks(employee.id()).isEmpty(), "New employees have no tasks");
        check(repository.findEmployees().stream().allMatch(u -> u.role().equals("EMPLOYEE")), "Only employees are assignable");

        repository.assignTask(admin.id(), employee.id(), "Weekly report", "Collect updates.\nShare the report.", LocalDate.now().plusDays(3));
        var task = repository.findTasks(employee.id()).getFirst();
        check(task.title().equals("Weekly report") && task.instructions().contains("Share the report."), "Employee sees the instructions");
        check(task.assignedBy() == admin.id() && task.status().equals("TODO"), "Task retains the assigning administrator");
        check(repository.findTasks(admin.id()).size() == 1, "Administrator sees assigned work");
        rejects(() -> repository.assignTask(employee.id(), employee.id(), "Invalid", "Details", null));
        rejects(() -> repository.assignTask(admin.id(), admin.id(), "Invalid", "Details", null));
        rejects(() -> repository.assignTask(admin.id(), 999, "Invalid", "Details", null));
        rejects(() -> repository.assignTask(admin.id(), employee.id(), " ", "Details", null));
        rejects(() -> repository.assignTask(admin.id(), employee.id(), "x".repeat(121), "Details", null));
        rejects(() -> repository.assignTask(admin.id(), employee.id(), "Invalid", " ", null));
        rejects(() -> repository.assignTask(admin.id(), employee.id(), "Invalid", "x".repeat(2001), null));
        rejects(() -> repository.assignTask(admin.id(), employee.id(), "Invalid", "Details", LocalDate.now().minusDays(1)));
        rejects(() -> repository.updateTaskStatus(admin.id(), task.id(), "COMPLETED"));
        rejects(() -> repository.updateTaskStatus(999, task.id(), "COMPLETED"));
        rejects(() -> repository.updateTaskStatus(employee.id(), 999, "COMPLETED"));
        rejects(() -> repository.updateTaskStatus(employee.id(), task.id(), "INVALID"));
        check(repository.findTasks(admin.id()).size() == 1, "Rejected assignments create no tasks");
        check(repository.findTasks(employee.id()).getFirst().status().equals("TODO"), "Rejected changes preserve progress");

        repository.updateTaskStatus(employee.id(), task.id(), "IN_PROGRESS");
        check(repository.findTasks(admin.id()).getFirst().status().equals("IN_PROGRESS"), "Administrator sees employee progress");
        repository.updateTaskStatus(employee.id(), task.id(), "COMPLETED");
        repository.updateTaskStatus(employee.id(), task.id(), "COMPLETED");
        repository.assignTask(admin.id(), employee.id(), "Next task", "No deadline", null);
        var tasks = repository.findTasks(employee.id());
        check(tasks.getFirst().dueDate() == null && tasks.getFirst().status().equals("TODO"), "Open tasks sort before completed tasks");
        check(tasks.get(1).status().equals("COMPLETED"), "Completed task is retained");
        System.out.println("Java task workflow checks passed.");
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }

    private static void rejects(Runnable action) {
        try { action.run(); }
        catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Invalid task operation was accepted");
    }
}
