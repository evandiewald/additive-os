import AMProject from 0x4263f3e1effb2e48

// This transaction allows the Minter account to mint an NFT
// and deposit it into its collection.

transaction() {

    // let myProject: @AMProject.Project
    // let collectionRef: &AMProject.Collection

    prepare(acct: AuthAccount) {
        let collectionResource <- acct.load<@AMProject.Collection>(from: /storage/AMProjects)
        destroy collectionResource
    }

    execute {
        
    }
}