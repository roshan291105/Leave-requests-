package com.leavems;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Cursor;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GradientPaint;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.LayoutManager;
import java.awt.RenderingHints;
import java.awt.geom.RoundRectangle2D;
import java.sql.Connection;
import java.sql.Date;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.DefaultListCellRenderer;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JComboBox;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JList;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JPasswordField;
import javax.swing.JScrollPane;
import javax.swing.JSplitPane;
import javax.swing.JTabbedPane;
import javax.swing.JTable;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.ListSelectionModel;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;
import javax.swing.WindowConstants;
import javax.swing.border.EmptyBorder;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.DefaultTableModel;

public final class LeaveManagementApp {
    private static final Color NAVY = new Color(15, 23, 42);
    private static final Color BLUE = new Color(99, 102, 241);
    private static final Color PURPLE = new Color(139, 92, 246);
    private static final Color CYAN = new Color(34, 211, 238);
    private static final Color BG = new Color(241, 245, 249);
    private static final Color TEXT_MUTED = new Color(100, 116, 139);
    private static final List<DemoEmployee> DEMO_EMPLOYEES = List.of(
            new DemoEmployee("DYO001", "employee", "Kavin", "Permanent"),
            new DemoEmployee("DYO002", "jordan", "Arul", "Permanent"),
            new DemoEmployee("DYO003", "priya", "Nila", "Permanent"),
            new DemoEmployee("DYO004", "arjun", "Thamizh", "Contract"),
            new DemoEmployee("DYO005", "ananya", "Kayal", "Permanent"),
            new DemoEmployee("DYO006", "rohan", "Ezhil", "Permanent"),
            new DemoEmployee("DYO007", "meera", "Malar", "Permanent"),
            new DemoEmployee("DYO008", "vikram", "Iniyan", "Contract"),
            new DemoEmployee("DYO009", "kavya", "Yazhini", "Intern"),
            new DemoEmployee("DYO010", "aditya", "Cheran", "Part-time"),
            new DemoEmployee("DYO011", "isha", "Thenmozhi", "Intern"),
            new DemoEmployee("DYO012", "rahul", "Kathir", "Permanent"),
            new DemoEmployee("DYO013", "sneha", "Thamarai", "Permanent"),
            new DemoEmployee("DYO014", "naveen", "Kumaran", "Probation"),
            new DemoEmployee("DYO015", "divya", "Vennila", "Intern"),
            new DemoEmployee("DYO016", "karan", "Senthil", "Contract"),
            new DemoEmployee("DYO017", "aisha", "Oviya", "Probation"),
            new DemoEmployee("DYO018", "siddharth", "Sezhiyan", "Permanent"),
            new DemoEmployee("DYO019", "neha", "Poongodi", "Part-time"),
            new DemoEmployee("DYO020", "varun", "Velan", "Permanent"));
    private static final List<String> TASK_TITLE_SUGGESTIONS = List.of(
            "Prepare the Weekly Project Status Report",
            "Review and Update Employee Attendance Records",
            "Complete Application Testing and Document Findings",
            "Resolve Outstanding Customer Support Requests",
            "Reconcile Monthly Expenses and Submit a Summary",
            "Update Project Documentation and User Guides",
            "Prepare the Monthly Sales Performance Report",
            "Develop the Upcoming Social Media Content Calendar",
            "Review Inventory Levels and Report Shortages",
            "Complete Required Training and Submit a Progress Update");
    private final JFrame frame = new JFrame("Employee Leave Management System");
    private final LeaveRepository repository;

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            UIManager.put("Button.font", new Font("Segoe UI", Font.BOLD, 13));
            UIManager.put("Label.font", new Font("SansSerif", Font.PLAIN, 13));
            UIManager.put("TextField.font", new Font("SansSerif", Font.PLAIN, 13));
            UIManager.put("TabbedPane.selected", Color.WHITE);
            UIManager.put("TabbedPane.contentAreaColor", BG);
            UIManager.put("TabbedPane.focus", new Color(0,0,0,0));
            UIManager.put("Table.selectionBackground", new Color(224, 231, 255));
            UIManager.put("Table.selectionForeground", NAVY);
            new LeaveManagementApp().showLogin();
        });
    }

    LeaveManagementApp() {
        repository = RepositoryFactory.create();
        frame.setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
        frame.setMinimumSize(new Dimension(950, 620));
        frame.setLocationRelativeTo(null);
    }

    private void showLogin() {
        JPanel root = new GradientPanel(new BorderLayout(), NAVY, new Color(49, 46, 129));
        root.setBackground(BG);
        JPanel brand = new JPanel(); brand.setOpaque(false); brand.setLayout(new BoxLayout(brand, BoxLayout.Y_AXIS));
        brand.setBorder(new EmptyBorder(110, 80, 80, 45));
        JLabel mark = new JLabel("◒  DAYORA"); mark.setForeground(CYAN); mark.setFont(new Font("Segoe UI", Font.BOLD, 18)); mark.setAlignmentX(Component.LEFT_ALIGNMENT);
        JLabel hero = new JLabel("<html>Leave, made<br>beautifully simple.</html>"); hero.setForeground(Color.WHITE); hero.setFont(new Font("Segoe UI", Font.BOLD, 40)); hero.setAlignmentX(Component.LEFT_ALIGNMENT);
        JLabel copy = new JLabel("<html>A calm workspace for your team to plan time away,<br>stay aligned, and return refreshed.</html>"); copy.setForeground(new Color(203,213,225)); copy.setFont(new Font("Segoe UI", Font.PLAIN, 15)); copy.setAlignmentX(Component.LEFT_ALIGNMENT);
        brand.add(mark); brand.add(Box.createVerticalStrut(35)); brand.add(hero); brand.add(Box.createVerticalStrut(22)); brand.add(copy);
        root.add(brand, BorderLayout.CENTER);
        JPanel loginWrap = new JPanel(new GridBagLayout()); loginWrap.setOpaque(false); loginWrap.setBorder(new EmptyBorder(55,35,55,70));
        JPanel card = new RoundPanel(28, Color.WHITE); card.setLayout(new GridBagLayout()); card.setBorder(new EmptyBorder(42, 44, 42, 44));
        GridBagConstraints c = constraints();
        JLabel eyebrow = new JLabel("WELCOME BACK"); eyebrow.setForeground(BLUE); eyebrow.setFont(new Font("Segoe UI",Font.BOLD,11));
        add(card, eyebrow, c, 0, 0, 2);
        JLabel title = new JLabel("Sign in to Dayora"); title.setFont(new Font("Segoe UI", Font.BOLD, 27)); title.setForeground(NAVY);
        add(card, title, c, 0, 1, 2); c.insets = new Insets(15, 5, 5, 5);
        add(card, new JLabel("Username"), c, 0, 2, 2);
        JTextField username = new JTextField(22); styleInput(username); add(card, username, c, 0, 3, 2);
        add(card, new JLabel("Password"), c, 0, 4, 2);
        JPasswordField password = new JPasswordField(22); styleInput(password); add(card, password, c, 0, 5, 2);
        JButton login = primaryButton("Continue  →"); add(card, login, c, 0, 6, 2);
        JLabel mode = new JLabel(repository.description()); mode.setForeground(Color.GRAY);
        add(card, mode, c, 0, 7, 2);
        login.addActionListener(e -> {
            User user = repository.authenticate(username.getText().trim(), new String(password.getPassword()));
            if (user == null) message("Invalid username or password.", JOptionPane.ERROR_MESSAGE);
            else if (user.role().equals("ADMIN")) showAdmin(user); else showEmployee(user);
        });
        password.addActionListener(e -> login.doClick());
        loginWrap.add(card); root.add(loginWrap, BorderLayout.EAST); setContent(root, new Dimension(1080, 680));
    }

    private void showEmployee(User user) {
        JPanel root = shell("Employee Dashboard", user);
        JTabbedPane tabs = styledTabs();
        JPanel requests = new JPanel(new BorderLayout(14, 14)); requests.setBackground(BG); requests.setBorder(new EmptyBorder(24,28,28,28));
        DefaultTableModel model = tableModel("ID", "Type", "From", "To", "Days", "Status", "Admin comment");
        JTable table = table(model); requests.add(new JScrollPane(table), BorderLayout.CENTER);
        JPanel stats = new JPanel(new FlowLayout(FlowLayout.LEFT, 14, 4)); stats.setOpaque(false); requests.add(stats, BorderLayout.NORTH);
        Runnable refresh = () -> {
            model.setRowCount(0); List<LeaveRequest> list = repository.findForEmployee(user.id());
            long pending = 0, approved = 0, rejected = 0;
            for (LeaveRequest r : list) {
                model.addRow(new Object[]{r.id(), r.type(), r.start(), r.end(), r.days(), r.status(), r.comment()});
                if (r.status().equals("PENDING")) pending++; else if (r.status().equals("APPROVED")) approved++; else rejected++;
            }
            stats.removeAll(); stats.add(stat("AWAITING REVIEW", pending, new Color(245,158,11))); stats.add(stat("APPROVED", approved, new Color(16,185,129))); stats.add(stat("DECLINED", rejected, new Color(244,63,94))); stats.revalidate();
        };
        JButton refreshButton = new JButton("Refresh"); refreshButton.addActionListener(e -> refresh.run());
        requests.add(refreshButton, BorderLayout.SOUTH);
        tabs.addTab("My requests", requests);
        tabs.addTab("Apply for leave", applicationForm(user, () -> { refresh.run(); tabs.setSelectedIndex(0); }));
        tabs.addTab("My tasks", taskPanel(user));
        root.add(tabs, BorderLayout.CENTER); refresh.run(); setContent(root, new Dimension(1050, 680));
    }

    private JPanel applicationForm(User user, Runnable afterSave) {
        JPanel outer = new JPanel(new GridBagLayout()); outer.setBackground(BG);
        JPanel form = new RoundPanel(24, Color.WHITE); form.setLayout(new GridBagLayout()); form.setBorder(new EmptyBorder(32,42,32,42));
        GridBagConstraints c = constraints();
        JComboBox<String> type = new JComboBox<>(new String[]{"Annual", "Sick", "Casual", "Unpaid"});
        JTextField start = new JTextField(LocalDate.now().toString(), 18), end = new JTextField(LocalDate.now().toString(), 18);
        JTextArea reason = new JTextArea(5, 24); reason.setLineWrap(true); reason.setWrapStyleWord(true);
        styleInput(start); styleInput(end); reason.setFont(new Font("Segoe UI",Font.PLAIN,14)); reason.setBorder(new EmptyBorder(10,12,10,12));
        add(form, new JLabel("Leave type"), c, 0, 0, 1); add(form, type, c, 1, 0, 1);
        add(form, new JLabel("Start date (YYYY-MM-DD)"), c, 0, 1, 1); add(form, start, c, 1, 1, 1);
        add(form, new JLabel("End date (YYYY-MM-DD)"), c, 0, 2, 1); add(form, end, c, 1, 2, 1);
        add(form, new JLabel("Reason"), c, 0, 3, 1); add(form, new JScrollPane(reason), c, 1, 3, 1);
        JButton submit = primaryButton("Submit request"); add(form, submit, c, 1, 4, 1);
        submit.addActionListener(e -> {
            try {
                LocalDate from = LocalDate.parse(start.getText().trim()), to = LocalDate.parse(end.getText().trim());
                if (to.isBefore(from)) throw new IllegalArgumentException("End date cannot be before start date.");
                if (reason.getText().isBlank()) throw new IllegalArgumentException("Please enter a reason.");
                repository.create(user.id(), Objects.toString(type.getSelectedItem()), from, to, reason.getText().trim());
                message("Leave request submitted.", JOptionPane.INFORMATION_MESSAGE); reason.setText(""); afterSave.run();
            } catch (Exception ex) { message(ex.getMessage() == null ? "Use valid dates in YYYY-MM-DD format." : ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
        });
        outer.add(form); return outer;
    }

    private void showAdmin(User user) {
        JPanel root = shell("Administrator Dashboard", user);
        JPanel body = new JPanel(new BorderLayout(14,14)); body.setBackground(BG); body.setBorder(new EmptyBorder(24,28,28,28));
        DefaultTableModel model = tableModel("ID", "Employee", "Type", "From", "To", "Days", "Reason", "Status", "Comment");
        JTable table = table(model); body.add(new JScrollPane(table), BorderLayout.CENTER);
        JCheckBox pendingOnly = new JCheckBox("Show pending only", true);
        Runnable refresh = () -> {
            model.setRowCount(0);
            for (LeaveRequest r : repository.findAll(pendingOnly.isSelected()))
                model.addRow(new Object[]{r.id(), r.employee(), r.type(), r.start(), r.end(), r.days(), r.reason(), r.status(), r.comment()});
        };
        pendingOnly.addActionListener(e -> refresh.run()); body.add(pendingOnly, BorderLayout.NORTH);
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.RIGHT)); actions.setOpaque(false);
        JButton refreshBtn = new JButton("Refresh"), reject = new JButton("Reject"), approve = primaryButton("Approve");
        actions.add(refreshBtn); actions.add(reject); actions.add(approve); body.add(actions, BorderLayout.SOUTH);
        refreshBtn.addActionListener(e -> refresh.run());
        approve.addActionListener(e -> decide(table, model, "APPROVED", refresh));
        reject.addActionListener(e -> decide(table, model, "REJECTED", refresh));
        JTabbedPane tabs = styledTabs();
        tabs.addTab("Leave requests", body);
        tabs.addTab("Team tasks", taskPanel(user));
        root.add(tabs, BorderLayout.CENTER); refresh.run(); setContent(root, new Dimension(1150, 700));
    }

    private JPanel taskPanel(User user) {
        JPanel panel = new JPanel(new BorderLayout(16, 16));
        panel.setBackground(BG); panel.setBorder(new EmptyBorder(24, 28, 28, 28));
        DefaultTableModel model = tableModel("ID", "Task", "Employee", "Assigned by", "Due date", "Progress");
        JTable taskTable = table(model);
        List<AssignedTask> visibleTasks = new ArrayList<>();
        JTextArea details = new JTextArea(6, 24);
        details.setEditable(false); details.setLineWrap(true); details.setWrapStyleWord(true);
        details.setFont(new Font("Segoe UI", Font.PLAIN, 14)); details.setBorder(new EmptyBorder(12, 12, 12, 12));
        JComboBox<String> progress = new JComboBox<>(new String[]{"To do", "In progress", "Completed"});
        taskTable.getSelectionModel().addListSelectionListener(e -> {
            if (e.getValueIsAdjusting() || taskTable.getSelectedRow() < 0) return;
            AssignedTask task = visibleTasks.get(taskTable.convertRowIndexToModel(taskTable.getSelectedRow()));
            details.setText(task.title() + "\n\n" + task.instructions()); details.setCaretPosition(0);
            progress.setSelectedItem(taskStatusLabel(task.status()));
        });
        Runnable refresh = () -> {
            try {
                List<AssignedTask> updated = repository.findTasks(user.id());
                model.setRowCount(0); visibleTasks.clear(); visibleTasks.addAll(updated);
                for (AssignedTask task : visibleTasks)
                    model.addRow(new Object[]{task.id(), task.title(), task.employee(), task.admin(),
                            task.dueDate() == null ? "No due date" : task.dueDate().toString(), taskStatusLabel(task.status())});
                details.setText(visibleTasks.isEmpty() ? "No tasks assigned yet." : "Select a task to read its instructions.");
            } catch (Exception ex) { message(ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
        };
        JPanel list = new JPanel(new BorderLayout(12, 12)); list.setOpaque(false);
        JSplitPane taskDetails = new JSplitPane(JSplitPane.VERTICAL_SPLIT, new JScrollPane(taskTable), new JScrollPane(details));
        taskDetails.setResizeWeight(.65); taskDetails.setBorder(null);
        list.add(taskDetails, BorderLayout.CENTER);
        JPanel actions = new JPanel(new FlowLayout(FlowLayout.RIGHT)); actions.setOpaque(false);
        JButton refreshButton = new JButton("Refresh tasks"); refreshButton.addActionListener(e -> refresh.run());
        actions.add(refreshButton);
        if (user.role().equals("EMPLOYEE")) {
            JButton update = primaryButton("Update progress");
            actions.add(progress); actions.add(update);
            update.addActionListener(e -> {
                if (taskTable.getSelectedRow() < 0) { message("Select a task first.", JOptionPane.WARNING_MESSAGE); return; }
                AssignedTask task = visibleTasks.get(taskTable.convertRowIndexToModel(taskTable.getSelectedRow()));
                String status = switch (progress.getSelectedIndex()) { case 1 -> "IN_PROGRESS"; case 2 -> "COMPLETED"; default -> "TODO"; };
                try { repository.updateTaskStatus(user.id(), task.id(), status); refresh.run(); }
                catch (Exception ex) { message(ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
            });
        }
        list.add(actions, BorderLayout.SOUTH);
        if (user.role().equals("ADMIN")) {
            JSplitPane split = new JSplitPane(JSplitPane.HORIZONTAL_SPLIT, taskAssignmentForm(user, refresh), list);
            split.setDividerLocation(330); split.setBorder(null); panel.add(split, BorderLayout.CENTER);
        } else panel.add(list, BorderLayout.CENTER);
        refresh.run(); return panel;
    }

    private JPanel taskAssignmentForm(User admin, Runnable afterSave) {
        JPanel outer = new JPanel(new BorderLayout()); outer.setOpaque(false);
        JPanel form = new RoundPanel(20, Color.WHITE); form.setLayout(new GridBagLayout());
        form.setBorder(new EmptyBorder(18, 18, 18, 18)); GridBagConstraints c = constraints(); c.weightx = 1;
        JComboBox<User> employee = new JComboBox<>();
        employee.setRenderer(new DefaultListCellRenderer() {
            public Component getListCellRendererComponent(JList<?> list, Object value, int index, boolean selected, boolean focus) {
                String label = value instanceof User person ? person.name() + " (" + person.username() + ")" : "Choose an employee";
                return super.getListCellRendererComponent(list, label, index, selected, focus);
            }
        });
        try { for (User person : repository.findEmployees()) employee.addItem(person); }
        catch (Exception ex) { message(ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
        employee.setSelectedIndex(-1);
        JTextField title = new JTextField(18), due = new JTextField(18); styleInput(title); styleInput(due);
        JComboBox<String> titleChoice = new JComboBox<>();
        titleChoice.addItem("Custom title"); TASK_TITLE_SUGGESTIONS.forEach(titleChoice::addItem);
        titleChoice.setPrototypeDisplayValue("Choose a title or write your own");
        titleChoice.getAccessibleContext().setAccessibleName("Task title");
        title.getAccessibleContext().setAccessibleName("Custom task title");
        title.setToolTipText("Enter a custom task title (up to 120 characters).");
        JPanel titleFields = new JPanel(new BorderLayout(0, 8)); titleFields.setOpaque(false);
        titleFields.add(titleChoice, BorderLayout.NORTH); titleFields.add(title, BorderLayout.CENTER);
        titleChoice.addActionListener(e -> {
            boolean custom = titleChoice.getSelectedIndex() == 0;
            title.setVisible(custom);
            titleChoice.setToolTipText(Objects.toString(titleChoice.getSelectedItem()));
            titleFields.revalidate(); form.revalidate(); form.repaint();
            if (custom) title.requestFocusInWindow();
        });
        JTextArea instructions = new JTextArea(6, 18); instructions.setLineWrap(true); instructions.setWrapStyleWord(true);
        instructions.setFont(new Font("Segoe UI", Font.PLAIN, 14));
        add(form, new JLabel("Assign a task"), c, 0, 0, 1);
        add(form, new JLabel("Employee"), c, 0, 1, 1); add(form, employee, c, 0, 2, 1);
        add(form, new JLabel("Task title (choose or write your own)"), c, 0, 3, 1); add(form, titleFields, c, 0, 4, 1);
        add(form, new JLabel("Instructions (up to 2,000 characters)"), c, 0, 5, 1); add(form, new JScrollPane(instructions), c, 0, 6, 1);
        add(form, new JLabel("Due date (optional, YYYY-MM-DD)"), c, 0, 7, 1); add(form, due, c, 0, 8, 1);
        JButton assign = primaryButton("Assign task"); assign.setEnabled(employee.getItemCount() > 0); add(form, assign, c, 0, 9, 1);
        assign.addActionListener(e -> {
            try {
                User selected = (User) employee.getSelectedItem();
                if (selected == null) throw new IllegalArgumentException("Choose an employee.");
                LocalDate dueDate = due.getText().isBlank() ? null : LocalDate.parse(due.getText().trim());
                String taskTitle = titleChoice.getSelectedIndex() == 0 ? title.getText().trim() : Objects.toString(titleChoice.getSelectedItem());
                repository.assignTask(admin.id(), selected.id(), taskTitle, instructions.getText().trim(), dueDate);
                title.setText(""); titleChoice.setSelectedIndex(0); instructions.setText(""); due.setText(""); afterSave.run();
                message("Task assigned to " + selected.name() + ".", JOptionPane.INFORMATION_MESSAGE);
            } catch (java.time.format.DateTimeParseException ex) { message("Use a valid due date in YYYY-MM-DD format.", JOptionPane.ERROR_MESSAGE); }
            catch (Exception ex) { message(ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
        });
        outer.add(form, BorderLayout.NORTH); return outer;
    }

    private static String taskStatusLabel(String status) {
        return switch (status) { case "IN_PROGRESS" -> "In progress"; case "COMPLETED" -> "Completed"; default -> "To do"; };
    }

    private static void validateTask(String title, String instructions, LocalDate dueDate) {
        if (title == null || title.isBlank() || title.length() > 120) throw new IllegalArgumentException("Enter a task title between 1 and 120 characters.");
        if (instructions == null || instructions.isBlank() || instructions.length() > 2000) throw new IllegalArgumentException("Enter instructions between 1 and 2,000 characters.");
        if (dueDate != null && dueDate.isBefore(LocalDate.now())) throw new IllegalArgumentException("The due date cannot be in the past.");
    }

    private static void validateTaskStatus(String status) {
        if (!List.of("TODO", "IN_PROGRESS", "COMPLETED").contains(status)) throw new IllegalArgumentException("Select a valid task status.");
    }

    private void decide(JTable table, DefaultTableModel model, String status, Runnable refresh) {
        int row = table.getSelectedRow();
        if (row < 0) { message("Select a request first.", JOptionPane.WARNING_MESSAGE); return; }
        long id = ((Number) model.getValueAt(table.convertRowIndexToModel(row), 0)).longValue();
        String comment = JOptionPane.showInputDialog(frame, "Administrator comment (optional):", status.substring(0,1) + status.substring(1).toLowerCase());
        if (comment == null) return;
        try { repository.decide(id, status, comment.trim()); refresh.run(); message("Request " + status.toLowerCase() + ".", JOptionPane.INFORMATION_MESSAGE); }
        catch (Exception ex) { message(ex.getMessage(), JOptionPane.ERROR_MESSAGE); }
    }

    private JPanel shell(String title, User user) {
        JPanel root = new JPanel(new BorderLayout()); root.setBackground(BG);
        JPanel header = new GradientPanel(new BorderLayout(), NAVY, new Color(49,46,129)); header.setBorder(new EmptyBorder(18,28,18,28));
        JPanel identity = new JPanel(); identity.setOpaque(false); identity.setLayout(new BoxLayout(identity,BoxLayout.Y_AXIS));
        JLabel logo = new JLabel("◒  DAYORA  /  PEOPLE"); logo.setForeground(CYAN); logo.setFont(new Font("Segoe UI",Font.BOLD,11));
        JLabel heading = new JLabel(title); heading.setForeground(Color.WHITE); heading.setFont(new Font("Segoe UI", Font.BOLD, 23));
        identity.add(logo); identity.add(Box.createVerticalStrut(4)); identity.add(heading);
        JPanel right = new JPanel(new FlowLayout()); right.setOpaque(false); JLabel who = new JLabel(user.name()); who.setForeground(Color.WHITE);
        JButton logout = new JButton("Logout"); logout.addActionListener(e -> showLogin()); right.add(who); right.add(logout);
        header.add(identity, BorderLayout.WEST); header.add(right, BorderLayout.EAST); root.add(header, BorderLayout.NORTH); return root;
    }

    private static JPanel stat(String label, long value, Color accent) { JPanel p=new RoundPanel(18,Color.WHITE);p.setLayout(new BorderLayout());p.setBorder(new EmptyBorder(14,18,14,22));JLabel n=new JLabel(String.valueOf(value));n.setFont(new Font("Segoe UI",Font.BOLD,25));n.setForeground(accent);JLabel l=new JLabel(label);l.setFont(new Font("Segoe UI",Font.BOLD,10));l.setForeground(TEXT_MUTED);p.add(n,BorderLayout.CENTER);p.add(l,BorderLayout.SOUTH);return p; }
    private static JTable table(DefaultTableModel m) { JTable t = new JTable(m); t.setRowHeight(38); t.setAutoCreateRowSorter(true); t.setSelectionMode(ListSelectionModel.SINGLE_SELECTION); t.setShowVerticalLines(false);t.setGridColor(new Color(226,232,240));t.setFont(new Font("Segoe UI",Font.PLAIN,13));t.getTableHeader().setFont(new Font("Segoe UI",Font.BOLD,11));t.getTableHeader().setBackground(new Color(248,250,252));t.getTableHeader().setForeground(TEXT_MUTED);t.getTableHeader().setPreferredSize(new Dimension(10,38));t.setDefaultRenderer(Object.class,new StatusRenderer()); return t; }
    private static DefaultTableModel tableModel(String... names) { return new DefaultTableModel(names, 0) { public boolean isCellEditable(int r, int c) { return false; } }; }
    private static JButton primaryButton(String text) { JButton b = new RoundButton(text, BLUE); b.setForeground(Color.WHITE); b.setFocusPainted(false); b.setBorder(new EmptyBorder(11,20,11,20)); return b; }
    private static void styleInput(JTextField field){field.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(new Color(203,213,225)),new EmptyBorder(10,12,10,12)));field.setBackground(new Color(248,250,252));}
    private static JTabbedPane styledTabs(){JTabbedPane t=new JTabbedPane();t.setFont(new Font("Segoe UI",Font.BOLD,13));t.setBackground(BG);t.setBorder(new EmptyBorder(8,18,0,18));return t;}
    private static GridBagConstraints constraints() { GridBagConstraints c = new GridBagConstraints(); c.insets = new Insets(7,5,7,5); c.fill = GridBagConstraints.HORIZONTAL; c.anchor = GridBagConstraints.WEST; return c; }
    private static void add(JPanel p, Component x, GridBagConstraints c, int gx, int gy, int width) { c.gridx=gx; c.gridy=gy; c.gridwidth=width; p.add(x,c); }
    private void setContent(JPanel panel, Dimension size) { frame.setContentPane(panel); frame.setSize(size); frame.setLocationRelativeTo(null); frame.setVisible(true); frame.revalidate(); }
    private void message(String text, int type) { JOptionPane.showMessageDialog(frame, text, "Leave Management", type); }

    static final class GradientPanel extends JPanel {
        private final Color from, to;
        GradientPanel(LayoutManager layout, Color from, Color to){super(layout);this.from=from;this.to=to;setOpaque(false);}
        protected void paintComponent(Graphics g){Graphics2D g2=(Graphics2D)g.create();g2.setRenderingHint(RenderingHints.KEY_RENDERING,RenderingHints.VALUE_RENDER_QUALITY);g2.setPaint(new GradientPaint(0,0,from,getWidth(),getHeight(),to));g2.fillRect(0,0,getWidth(),getHeight());g2.dispose();super.paintComponent(g);}
    }

    static class RoundPanel extends JPanel {
        private final int radius; private final Color fill;
        RoundPanel(int radius,Color fill){this.radius=radius;this.fill=fill;setOpaque(false);}
        protected void paintComponent(Graphics g){Graphics2D g2=(Graphics2D)g.create();g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);g2.setColor(new Color(15,23,42,18));g2.fillRoundRect(2,4,getWidth()-4,getHeight()-5,radius,radius);g2.setColor(fill);g2.fillRoundRect(0,0,getWidth()-3,getHeight()-4,radius,radius);g2.dispose();super.paintComponent(g);}
    }

    static final class RoundButton extends JButton {
        private final Color fill;
        RoundButton(String text,Color fill){super(text);this.fill=fill;setContentAreaFilled(false);setOpaque(false);setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));}
        protected void paintComponent(Graphics g){Graphics2D g2=(Graphics2D)g.create();g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);g2.setColor(getModel().isPressed()?fill.darker():getModel().isRollover()?fill.brighter():fill);g2.fill(new RoundRectangle2D.Float(0,0,getWidth(),getHeight(),14,14));g2.dispose();super.paintComponent(g);}
    }

    static final class StatusRenderer extends DefaultTableCellRenderer {
        public Component getTableCellRendererComponent(JTable table,Object value,boolean selected,boolean focus,int row,int col){
            JLabel label=(JLabel)super.getTableCellRendererComponent(table,value,selected,focus,row,col);label.setBorder(new EmptyBorder(0,10,0,10));
            if(!selected){label.setBackground(row%2==0?Color.WHITE:new Color(248,250,252));label.setForeground(NAVY);}
            String text=Objects.toString(value,"");
            if(!selected&&text.equals("APPROVED"))label.setForeground(new Color(5,150,105));
            else if(!selected&&text.equals("REJECTED"))label.setForeground(new Color(225,29,72));
            else if(!selected&&text.equals("PENDING"))label.setForeground(new Color(217,119,6));
            return label;
        }
    }

    record User(long id, String username, String name, String role) {}
    record DemoEmployee(String code, String legacyUsername, String name, String employmentType) {}
    record AssignedTask(long id, long employeeId, String employee, long assignedBy, String admin,
                        String title, String instructions, LocalDate dueDate, String status) {}
    record LeaveRequest(long id, long employeeId, String employee, String type, LocalDate start, LocalDate end, String reason, String status, String comment) {
        long days() { return ChronoUnit.DAYS.between(start, end) + 1; }
    }

    interface LeaveRepository {
        User authenticate(String username, String password);
        void create(long employeeId, String type, LocalDate start, LocalDate end, String reason);
        List<LeaveRequest> findForEmployee(long employeeId);
        List<LeaveRequest> findAll(boolean pendingOnly);
        void decide(long id, String status, String comment);
        List<User> findEmployees();
        void assignTask(long adminId, long employeeId, String title, String instructions, LocalDate dueDate);
        List<AssignedTask> findTasks(long viewerId);
        void updateTaskStatus(long employeeId, long taskId, String status);
        String description();
    }

    static final class RepositoryFactory {
        static LeaveRepository create() {
            String url = System.getenv().getOrDefault("LEAVE_DB_URL", "jdbc:mysql://localhost:3306/leave_management");
            try { JdbcRepository repo = new JdbcRepository(url, System.getenv().getOrDefault("LEAVE_DB_USER", "root"), System.getenv().getOrDefault("LEAVE_DB_PASSWORD", "")); repo.test(); return repo; }
            catch (Exception ignored) { return new MemoryRepository(); }
        }
    }

    static final class JdbcRepository implements LeaveRepository {
        private final String url, user, password;
        JdbcRepository(String url, String user, String password) { this.url=url; this.user=user; this.password=password; }
        Connection connection() throws SQLException { return DriverManager.getConnection(url, user, password); }
        void test() throws SQLException {
            try (Connection c = connection(); Statement statement = c.createStatement()) {
                statement.executeUpdate("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        employee_id BIGINT NOT NULL,
                        assigned_by BIGINT NOT NULL,
                        title VARCHAR(120) NOT NULL,
                        instructions VARCHAR(2000) NOT NULL,
                        due_date DATE NULL,
                        status ENUM('TODO','IN_PROGRESS','COMPLETED') NOT NULL DEFAULT 'TODO',
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (employee_id) REFERENCES users(id),
                        FOREIGN KEY (assigned_by) REFERENCES users(id)
                    )
                    """);
                migrateEmployeeNames(c);
            }
        }
        private void migrateEmployeeNames(Connection c) throws SQLException {
            try (Statement statement = c.createStatement()) {
                statement.executeUpdate("CREATE TABLE IF NOT EXISTS app_migrations (name VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)");
            }
            c.setAutoCommit(false);
            try {
                try (PreparedStatement p = c.prepareStatement("SELECT 1 FROM app_migrations WHERE name='tamil_employee_names_v1'"); ResultSet r = p.executeQuery()) {
                    if (r.next()) { c.commit(); return; }
                }
                for (DemoEmployee demo : DEMO_EMPLOYEES) {
                    Long employeeId = null;
                    try (PreparedStatement p = c.prepareStatement("SELECT id FROM users WHERE role='EMPLOYEE' AND (employee_code=? OR (employee_code IS NULL AND username IN (?,?))) ORDER BY id LIMIT 1")) {
                        p.setString(1, demo.code()); p.setString(2, demo.legacyUsername()); p.setString(3, demo.name());
                        try (ResultSet r = p.executeQuery()) { if (r.next()) employeeId = r.getLong(1); }
                    }
                    if (employeeId != null) {
                        try (PreparedStatement p = c.prepareStatement("UPDATE users SET username=?,password=?,full_name=?,employee_code=? WHERE id=?")) {
                            p.setString(1, demo.name()); p.setString(2, demo.name()); p.setString(3, demo.name());
                            p.setString(4, demo.code()); p.setLong(5, employeeId); p.executeUpdate();
                        }
                    } else {
                        try (PreparedStatement p = c.prepareStatement("INSERT INTO users(username,password,full_name,role,employee_code,employment_type) VALUES(?,?,?,'EMPLOYEE',?,?)")) {
                            p.setString(1, demo.name()); p.setString(2, demo.name()); p.setString(3, demo.name());
                            p.setString(4, demo.code()); p.setString(5, demo.employmentType()); p.executeUpdate();
                        }
                    }
                }
                try (PreparedStatement p = c.prepareStatement("INSERT INTO app_migrations(name) VALUES('tamil_employee_names_v1')")) { p.executeUpdate(); }
                c.commit();
            } catch (SQLException e) { c.rollback(); throw e; }
            finally { c.setAutoCommit(true); }
        }
        public User authenticate(String username, String password) {
            String sql="SELECT id,username,full_name,role FROM users WHERE CAST(username AS BINARY)=CAST(? AS BINARY) AND CAST(password AS BINARY)=CAST(? AS BINARY)";
            try(Connection c=connection(); PreparedStatement p=c.prepareStatement(sql)){ p.setString(1,username);p.setString(2,password);try(ResultSet r=p.executeQuery()){return r.next()?new User(r.getLong(1),r.getString(2),r.getString(3),r.getString(4)):null;}} catch(SQLException e){throw db(e);}
        }
        public void create(long eid,String type,LocalDate start,LocalDate end,String reason){String sql="INSERT INTO leave_requests(employee_id,leave_type,start_date,end_date,reason) VALUES(?,?,?,?,?)";try(Connection c=connection();PreparedStatement p=c.prepareStatement(sql)){p.setLong(1,eid);p.setString(2,type);p.setDate(3,Date.valueOf(start));p.setDate(4,Date.valueOf(end));p.setString(5,reason);p.executeUpdate();}catch(SQLException e){throw db(e);}}
        public List<LeaveRequest> findForEmployee(long id){return query("WHERE l.employee_id=? ORDER BY l.created_at DESC",p->p.setLong(1,id));}
        public List<LeaveRequest> findAll(boolean pending){return query((pending?"WHERE l.status='PENDING' ":"")+"ORDER BY l.created_at DESC",p->{});}
        private List<LeaveRequest> query(String suffix, SqlSetter setter){String sql="SELECT l.id,l.employee_id,u.full_name,l.leave_type,l.start_date,l.end_date,l.reason,l.status,COALESCE(l.admin_comment,'') FROM leave_requests l JOIN users u ON u.id=l.employee_id "+suffix;List<LeaveRequest>x=new ArrayList<>();try(Connection c=connection();PreparedStatement p=c.prepareStatement(sql)){setter.set(p);try(ResultSet r=p.executeQuery()){while(r.next())x.add(new LeaveRequest(r.getLong(1),r.getLong(2),r.getString(3),r.getString(4),r.getDate(5).toLocalDate(),r.getDate(6).toLocalDate(),r.getString(7),r.getString(8),r.getString(9)));}return x;}catch(SQLException e){throw db(e);}}
        public void decide(long id,String status,String comment){String sql="UPDATE leave_requests SET status=?,admin_comment=?,decided_at=CURRENT_TIMESTAMP WHERE id=? AND status='PENDING'";try(Connection c=connection();PreparedStatement p=c.prepareStatement(sql)){p.setString(1,status);p.setString(2,comment);p.setLong(3,id);if(p.executeUpdate()==0)throw new IllegalStateException("Request was already processed.");}catch(SQLException e){throw db(e);}}
        public List<User> findEmployees() {
            List<User> employees = new ArrayList<>();
            try (Connection c = connection(); PreparedStatement p = c.prepareStatement("SELECT id,username,full_name,role FROM users WHERE role='EMPLOYEE' ORDER BY full_name"); ResultSet r = p.executeQuery()) {
                while (r.next()) employees.add(new User(r.getLong(1), r.getString(2), r.getString(3), r.getString(4)));
                return employees;
            } catch (SQLException e) { throw db(e); }
        }
        public void assignTask(long adminId, long employeeId, String title, String instructions, LocalDate dueDate) {
            validateTask(title, instructions, dueDate);
            String sql = """
                INSERT INTO tasks(employee_id,assigned_by,title,instructions,due_date)
                SELECT e.id,a.id,?,?,? FROM users e CROSS JOIN users a
                WHERE e.id=? AND e.role='EMPLOYEE' AND a.id=? AND a.role='ADMIN'
                """;
            try (Connection c = connection(); PreparedStatement p = c.prepareStatement(sql)) {
                p.setString(1, title.trim()); p.setString(2, instructions.trim());
                p.setDate(3, dueDate == null ? null : Date.valueOf(dueDate)); p.setLong(4, employeeId); p.setLong(5, adminId);
                if (p.executeUpdate() == 0) throw new IllegalArgumentException("An administrator must assign the task to a valid employee.");
            } catch (SQLException e) { throw db(e); }
        }
        public List<AssignedTask> findTasks(long viewerId) {
            String sql = """
                SELECT t.id,t.employee_id,e.full_name,t.assigned_by,a.full_name,t.title,t.instructions,t.due_date,t.status
                FROM tasks t JOIN users e ON e.id=t.employee_id JOIN users a ON a.id=t.assigned_by
                JOIN users v ON v.id=? WHERE v.role='ADMIN' OR (v.role='EMPLOYEE' AND t.employee_id=v.id)
                ORDER BY (t.status='COMPLETED'), (t.due_date IS NULL), t.due_date, t.id DESC
                """;
            List<AssignedTask> tasks = new ArrayList<>();
            try (Connection c = connection(); PreparedStatement p = c.prepareStatement(sql)) {
                p.setLong(1, viewerId);
                try (ResultSet r = p.executeQuery()) {
                    while (r.next()) {
                        Date due = r.getDate(8);
                        tasks.add(new AssignedTask(r.getLong(1), r.getLong(2), r.getString(3), r.getLong(4), r.getString(5),
                                r.getString(6), r.getString(7), due == null ? null : due.toLocalDate(), r.getString(9)));
                    }
                }
                return tasks;
            } catch (SQLException e) { throw db(e); }
        }
        public void updateTaskStatus(long employeeId, long taskId, String status) {
            validateTaskStatus(status);
            String sql = """
                UPDATE tasks t JOIN users e ON e.id=t.employee_id
                SET t.status=?,t.updated_at=CURRENT_TIMESTAMP WHERE t.id=? AND e.id=? AND e.role='EMPLOYEE'
                """;
            try (Connection c = connection(); PreparedStatement p = c.prepareStatement(sql)) {
                p.setString(1, status); p.setLong(2, taskId); p.setLong(3, employeeId);
                if (p.executeUpdate() == 0) throw new IllegalArgumentException("Task not found for this employee.");
            } catch (SQLException e) { throw db(e); }
        }
        public String description(){return "Connected to MySQL";}
        private static RuntimeException db(SQLException e){return new IllegalStateException("Database error: "+e.getMessage(),e);}
        interface SqlSetter{void set(PreparedStatement p)throws SQLException;}
    }

    static final class MemoryRepository implements LeaveRepository {
        private final List<User> users = new ArrayList<>();
        MemoryRepository() {
            users.add(new User(1, "admin", "System Administrator", "ADMIN"));
            for (DemoEmployee employee : DEMO_EMPLOYEES)
                users.add(new User(users.size() + 1L, employee.name(), employee.name(), "EMPLOYEE"));
        }
        private final List<LeaveRequest> leaves=new ArrayList<>(); private long next=1;
        private final List<AssignedTask> tasks = new ArrayList<>(); private long nextTask = 1;
        public User authenticate(String u,String p){return users.stream().filter(x->x.username().equals(u)&&p.equals(x.role().equals("ADMIN")?"admin123":x.name())).findFirst().orElse(null);}
        public synchronized void create(long eid,String type,LocalDate start,LocalDate end,String reason){String name=users.stream().filter(u->u.id()==eid).findFirst().orElseThrow().name();leaves.add(new LeaveRequest(next++,eid,name,type,start,end,reason,"PENDING",""));}
        public synchronized List<LeaveRequest> findForEmployee(long eid){return leaves.stream().filter(x->x.employeeId()==eid).toList();}
        public synchronized List<LeaveRequest> findAll(boolean pending){return leaves.stream().filter(x->!pending||x.status().equals("PENDING")).toList();}
        public synchronized void decide(long id,String status,String comment){for(int i=0;i<leaves.size();i++){LeaveRequest x=leaves.get(i);if(x.id()==id){if(!x.status().equals("PENDING"))throw new IllegalStateException("Request was already processed.");leaves.set(i,new LeaveRequest(x.id(),x.employeeId(),x.employee(),x.type(),x.start(),x.end(),x.reason(),status,comment));return;}}throw new IllegalArgumentException("Request not found.");}
        public List<User> findEmployees() { return users.stream().filter(u -> u.role().equals("EMPLOYEE")).toList(); }
        private User requireUser(long id, String role) {
            return users.stream().filter(u -> u.id() == id && u.role().equals(role)).findFirst()
                    .orElseThrow(() -> new IllegalArgumentException("A valid " + role.toLowerCase() + " is required."));
        }
        public synchronized void assignTask(long adminId, long employeeId, String title, String instructions, LocalDate dueDate) {
            User admin = requireUser(adminId, "ADMIN"), employee = requireUser(employeeId, "EMPLOYEE");
            validateTask(title, instructions, dueDate);
            tasks.add(new AssignedTask(nextTask++, employeeId, employee.name(), adminId, admin.name(), title.trim(), instructions.trim(), dueDate, "TODO"));
        }
        public synchronized List<AssignedTask> findTasks(long viewerId) {
            User viewer = users.stream().filter(u -> u.id() == viewerId).findFirst()
                    .orElseThrow(() -> new IllegalArgumentException("User not found."));
            return tasks.stream().filter(t -> viewer.role().equals("ADMIN") || t.employeeId() == viewerId)
                    .sorted(java.util.Comparator.comparing((AssignedTask t) -> t.status().equals("COMPLETED"))
                            .thenComparing(AssignedTask::dueDate, java.util.Comparator.nullsLast(java.util.Comparator.naturalOrder()))
                            .thenComparing(java.util.Comparator.comparingLong(AssignedTask::id).reversed())).toList();
        }
        public synchronized void updateTaskStatus(long employeeId, long taskId, String status) {
            requireUser(employeeId, "EMPLOYEE"); validateTaskStatus(status);
            for (int i = 0; i < tasks.size(); i++) {
                AssignedTask task = tasks.get(i);
                if (task.id() == taskId && task.employeeId() == employeeId) {
                    tasks.set(i, new AssignedTask(task.id(), task.employeeId(), task.employee(), task.assignedBy(), task.admin(),
                            task.title(), task.instructions(), task.dueDate(), status));
                    return;
                }
            }
            throw new IllegalArgumentException("Task not found for this employee.");
        }
        public String description(){return "Demo mode (MySQL not connected)";}
    }
}
