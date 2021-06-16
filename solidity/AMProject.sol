// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.7.0 <0.9.0;

/** 
 * @title AMProject
 * @dev Stores project metadata such as file hashes
 */
contract AMProject {
   
    struct Project {
        address author;
        string[] files;
    }


    Project[] public projectList;
    mapping(uint256 => Project) projects;
    uint256 public projectCount = 0;
    



    function addProject(address _author) public returns (Project memory){
        Project storage new_project = projects[projectCount];
        new_project.author = _author;
        
        projectList.push(new_project);

        projectCount++;
        
        return projects[projectCount-1];
    }


    function addHash(uint _projectid, string memory _checksum) public returns (uint){
        
        projects[_projectid].files.push(_checksum);
        
        return projects[_projectid].files.length;
    }
    
    
    function getProject(uint _projectid) public view returns (Project memory) {
        require(_projectid < projectCount, "Project ID does not exist.");
        return projects[_projectid];
    }
    
    
    function getHash(uint _projectid, uint _fileid) public view returns (string memory) {
        require(_projectid < projectCount, "Project ID does not exist.");
        require(_fileid < projects[_projectid].files.length, "File ID does not exist.");
        return projects[_projectid].files[_fileid];
    }
    
    
    function listProjects() public view returns (Project[] memory) {
        return projectList;
    }
    
    
    function getProjectCount() public view returns (uint){
        return projectList.length;
    }
}
